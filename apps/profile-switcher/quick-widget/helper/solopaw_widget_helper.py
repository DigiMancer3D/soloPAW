#!/usr/bin/env python3
"""soloPAW Plasma widget bridge. Python standard library only.

Modes are intentionally single-shot. No background services or polling loops are
left running. The existing soloPAW configuration and Input Remapper presets are
used directly; no profiles are bundled or overwritten.
"""
from __future__ import annotations

import argparse
import ast
import fcntl
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get('SOLOPAW_WIDGET_CONFIG', str(HOME / '.config/solopaw-profile-switcher/config.json')))
ROOT = Path(os.environ.get('SOLOPAW_WIDGET_REMAP_ROOT', str(HOME / '.config/input-remapper-2')))
STATE_DIR = HOME / '.local/state/solopaw-profile-switcher-widget'
DEFAULT_DEVICE = 'Logitech G502 HERO Gaming Mouse'
DEST = 'inputremapper.Control'
OBJPATH = '/inputremapper/Control'
IFACE = 'inputremapper.Control'


def emit(ok: bool, message: str, **fields) -> int:
    print(json.dumps({'ok': ok, 'message': message, **fields}, ensure_ascii=False, separators=(',', ':')))
    return 0 if ok else 1


def config():
    if not CONFIG.is_file():
        raise RuntimeError('Profile Switcher config not found. Install/open soloPAW Profile Switcher and assign Quick Presets first.')
    try:
        cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
        if not isinstance(cfg, dict):
            raise ValueError('Config must be an object')
        slots = cfg.get('slots', [])
        if not isinstance(slots, list):
            raise ValueError('slots must be an array')
        return cfg
    except (OSError, ValueError) as exc:
        raise RuntimeError('Could not read Profile Switcher config: ' + str(exc)) from exc


def slot_items(cfg):
    aliases = cfg.get('common_names', {})
    if not isinstance(aliases, dict):
        aliases = {}
    device = str(cfg.get('device') or DEFAULT_DEVICE)
    result = []
    slots = cfg.get('slots', [])
    for idx in range(3):
        slot = slots[idx] if idx < len(slots) and isinstance(slots[idx], dict) else {}
        profile = str(slot.get('profile') or '').strip()
        label = str(slot.get('label') or aliases.get(profile) or (f'Quick Preset {idx+1}')).strip()
        # Preset filename must be a simple stem; prevent traversal even in a corrupt config.
        safe = bool(profile) and profile not in ('.', '..') and '/' not in profile and '\\' not in profile and '\x00' not in profile
        path = ROOT / 'presets' / device / (profile + '.json')
        result.append({'slot': idx + 1, 'profile': profile, 'label': label, 'loaded': bool(safe and path.is_file())})
    return device, result


def which(name, env_var=None):
    override = os.environ.get(env_var, '') if env_var else ''
    return override or shutil.which(name)


def bus_method(method: str, device: str | None = None, timeout=4.5):
    """Call read-only Input Remapper D-Bus method; preserve empty responses.

    The service expects a group *key*, not necessarily the human-readable name
    used for preset directory paths. `get_groups` takes no arguments.
    """
    busctl = which('busctl', 'SOLOPAW_WIDGET_BUSCTL')
    if not busctl:
        return False, 'busctl is missing'
    args = [busctl, '--system', '--no-pager', '--timeout=4', 'call', DEST, OBJPATH, IFACE, method]
    if device is not None:
        args.extend(['s', device])
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if p.returncode:
        return False, (p.stderr.strip() or p.stdout.strip() or 'D-Bus call failed')[:300]
    try:
        tokens = shlex.split(p.stdout.strip(), posix=True)
        if len(tokens) == 2 and tokens[0] == 's':
            return True, tokens[1]
    except ValueError:
        pass
    return False, 'Unexpected D-Bus response for ' + method


DEVICE_KEY_CACHE_SECONDS = 300


def group_entries(response: str):
    """Decode input-remapper group dumps, which are JSON arrays of JSON strings."""
    groups = json.loads(response)
    if not isinstance(groups, list):
        raise ValueError('Unexpected device group list')
    result = []
    for entry in groups:
        if isinstance(entry, str):
            entry = json.loads(entry)
        if isinstance(entry, dict) and isinstance(entry.get('key'), str):
            result.append(entry)
    return result


def read_key_cache(device: str):
    path = STATE_DIR / 'device-key.json'
    try:
        if time.time() - path.stat().st_mtime > DEVICE_KEY_CACHE_SECONDS:
            return None
        item = json.loads(path.read_text(encoding='utf-8'))
        if item.get('device') == device and isinstance(item.get('group_key'), str) and item['group_key']:
            return item['group_key']
    except (OSError, ValueError, KeyError, AttributeError):
        return None
    return None


def save_key_cache(device: str, key: str):
    """User-scoped cache only; never mutate Input Remapper device settings."""
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = STATE_DIR / 'device-key.json'
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix='.key-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump({'device': device, 'group_key': key}, f)
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError:
        pass


def resolve_group_key(device: str, force_refresh=False):
    """Resolve preset directory/group name to service key without guessing.

    The key may differ for duplicate or composite input devices. Legacy daemon
    builds without get_groups fall back to the configured device name.
    Returns (key, resolved, diagnostic).
    """
    if not force_refresh:
        cached = read_key_cache(device)
        if cached:
            return cached, True, 'cache'
    ok, groups_raw = bus_method('get_groups')
    if ok:
        try:
            entries = group_entries(groups_raw)
            # Prefer exact group key, then the normalized display name used in
            # preset directories, then member device names.
            for attr in ('key', 'name', 'names'):
                for entry in entries:
                    key = entry.get('key')
                    names = entry.get('names') or []
                    if not isinstance(names, list):
                        names = []
                    if attr == 'key' and key == device:
                        save_key_cache(device, key)
                        return key, True, 'groups'
                    if attr == 'name' and names and min(names, key=len) == device:
                        save_key_cache(device, key)
                        return key, True, 'groups'
                    if attr == 'names' and device in names:
                        save_key_cache(device, key)
                        return key, True, 'groups'
            return device, False, 'Device not found in live Input Remapper groups'
        except (ValueError, TypeError) as exc:
            return device, False, 'Could not decode live device groups: ' + str(exc)[:100]
    # Old services may omit get_groups. Direct-name probing remains a valid
    # read-only compatibility path, but positive results must be verified.
    return device, False, 'Device-group discovery unavailable: ' + groups_raw


def live_snapshot(device: str, refresh_group=False):
    key, resolved, origin = resolve_group_key(device, force_refresh=refresh_group)
    name_ok, preset = bus_method('get_running_preset', key)
    state_ok, state = bus_method('get_state', key)
    # 2.2.1 exposes get_state but neither get_running_preset nor get_groups.
    # In that case there IS usable evidence about injector activity, just not
    # a way to identify the active preset by name. Do not report false failure.
    state = state.upper() if state_ok else 'UNAVAILABLE'
    available = name_ok or state_ok
    reason = ''
    if not available:
        reason = 'Neither running-preset nor injector-state queries are available.'
    elif not name_ok:
        reason = 'Legacy Input Remapper: injector state only; exact preset name unavailable.'
    elif not resolved and not preset:
        reason = origin
    return {'detected': available, 'exact_available': name_ok,
            'group_key': key, 'resolved': resolved,
            'preset': preset if name_ok else '', 'state': state,
            'state_available': state_ok, 'reason': reason,
            'group_source': origin}


def confirmed_active(snapshot, profile: str):
    """Return only exact per-preset proof; legacy state-only stays separate."""
    if not snapshot['exact_available'] or snapshot['preset'] != profile:
        return False
    if not snapshot['state_available']:
        return True
    return snapshot['state'] == 'RUNNING'


def injector_running(snapshot):
    return snapshot['state_available'] and snapshot['state'] == 'RUNNING'



def installed_command():
    wrapper = HOME / '.local/bin/solopaw-profile-switcher'
    if wrapper.is_file() and os.access(wrapper, os.X_OK):
        return str(wrapper)
    return shutil.which('solopaw-profile-switcher')


def native_cli_supported():
    """Only use the application's CLI when evidence shows the flag is supported.

    Old v0.1 builds start a GUI for unrecognised flags, so probing by launching
    with --activate-slot is unsafe. Otherwise use Input Remapper's stable CLI.
    """
    if os.environ.get('SOLOPAW_WIDGET_FORCE_NATIVE_CLI') == '1':
        return True
    candidates = [HOME / '.local/share/solopaw-profile-switcher/solopaw_profile_switcher.py',
                  HOME / '.local/share/solopaw-profile-switcher/app.py',
                  HOME / '.local/share/solopaw-profile-switcher/profile_switcher.py']
    cmd = installed_command()
    if cmd:
        candidates.append(Path(cmd))
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size < 1_000_000 and '--activate-slot' in path.read_text(errors='replace'):
                return True
        except (OSError, UnicodeError):
            continue
    return False


def log_event(outcome, slot, detail):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = STATE_DIR / 'widget.log'
        if path.exists() and path.stat().st_size > 150_000:
            path.replace(STATE_DIR / 'widget.log.old')
        with path.open('a', encoding='utf-8') as file:
            file.write(json.dumps({'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                                   'outcome': outcome, 'slot': slot, 'detail': detail[:500]}) + '\n')
    except OSError:
        pass


def mark_last_active(profile):
    """Update the Switcher's display hint without replacing unrelated settings."""
    try:
        latest = json.loads(CONFIG.read_text(encoding='utf-8'))
        if latest.get('last_active_profile') == profile:
            return
        latest['last_active_profile'] = profile
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=CONFIG.parent, prefix='.widget-config-', suffix='.tmp')
        try:
            os.fchmod(fd, CONFIG.stat().st_mode & 0o777)
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump(latest, file, indent=2, ensure_ascii=False)
                file.write('\n')
            os.replace(tmp, CONFIG)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except (OSError, ValueError):
        # Cache is not proof of success; don't demote a verified activation.
        pass


def activate(index, wait_seconds=12):
    try:
        cfg = config()
        device, slots = slot_items(cfg)
    except RuntimeError as exc:
        return emit(False, str(exc), slot=index)
    item = slots[index - 1]
    if not item['profile']:
        return emit(False, 'Quick Preset %s is empty. Assign it in Profile Switcher.' % index, slot=index)
    if not item['loaded']:
        return emit(False, 'Preset file is missing for %s.' % item['label'], slot=index)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (STATE_DIR / 'activate.lock').open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return emit(False, 'Another profile switch is still in progress.', slot=index)
        ctrl = which('input-remapper-control', 'SOLOPAW_WIDGET_CONTROL')
        if not ctrl:
            return emit(False, 'input-remapper-control is unavailable.', slot=index)
        try:
            hello = subprocess.run([ctrl, '--command', 'hello'], text=True, capture_output=True,
                                   timeout=8, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return emit(False, 'Input Remapper service unavailable: ' + str(exc), slot=index)
        if hello.returncode:
            return emit(False, 'Input Remapper service did not respond to hello.', slot=index)

        cmd = [ctrl, '--command', 'start', '--device', device, '--preset', item['profile']]
        method = 'remapper'
        installed = installed_command()
        if installed and native_cli_supported():
            cmd = [installed, '--activate-slot', str(index)]
            method = 'switcher-cli'
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=28, check=False)
        except subprocess.TimeoutExpired:
            msg = 'Profile switch timed out before reporting completion.'
            log_event('error', index, msg)
            return emit(False, msg, slot=index)
        except OSError as exc:
            msg = 'Could not launch profile switch: ' + str(exc)
            log_event('error', index, msg)
            return emit(False, msg, slot=index)
        if proc.returncode:
            msg = (proc.stderr.strip() or proc.stdout.strip() or 'Profile switch failed')[:350]
            log_event('error', index, msg)
            return emit(False, msg, slot=index, backend=method)

        # Wait for the exact live injector to transition to RUNNING.
        # A successful CLI exit is not sufficient: start is asynchronous.
        deadline = time.monotonic() + wait_seconds
        last = None
        saw_live_reply = False
        saw_explicit_failure = False
        while True:
            now = time.monotonic()
            # Refresh group discovery at the first read. On second attempt,
            # repeat if we only got empty/unknown group state.
            snap = live_snapshot(device, refresh_group=(last is None))
            last = snap
            if snap['detected']:
                saw_live_reply = True
            if confirmed_active(snap, item['profile']):
                mark_last_active(item['profile'])
                log_event('verified', index, item['label'])
                return emit(True, item['label'] + ' is active.', slot=index,
                            outcome='verified', verified=True,
                            profile=item['profile'], backend=method)
            # Input Remapper 2.2.1 has get_state only. A successful request
            # followed by RUNNING means the injector is active, but we cannot
            # inspect its preset name. Show applied (not failed or verified).
            if not snap['exact_available'] and injector_running(snap):
                mark_last_active(item['profile'])
                log_event('applied-state-only', index, item['label'])
                return emit(True, item['label'] + ' applied; injector reports RUNNING. '
                            'This Input Remapper version cannot identify the preset name.',
                            slot=index, outcome='applied', verified=False,
                            profile=item['profile'], backend=method,
                            confidence='state-only')
            if snap['detected'] and snap['state_available'] and snap['state'] in ('FAILED', 'NO_GRAB', 'UPGRADE_EVDEV'):
                saw_explicit_failure = True
                # A transition can briefly expose the old injector state;
                # require a short grace period before deciding failure.
                if deadline - now <= wait_seconds - 1.2:
                    break
            if now >= deadline:
                break
            time.sleep(0.35)
        state = last['state'] if last else 'UNKNOWN'
        current = last['preset'] if last else ''
        if saw_explicit_failure and state in ('FAILED', 'NO_GRAB', 'UPGRADE_EVDEV'):
            msg = 'Input Remapper reported ' + state + ' while applying ' + item['label'] + '.'
            outcome = 'failed'
        elif saw_live_reply and state in ('STARTING', 'UNKNOWN') and current == item['profile']:
            msg = 'Profile was requested but injector did not confirm RUNNING in time.'
            outcome = 'unverified'
        elif saw_live_reply and last['resolved'] and (current != item['profile']):
            msg = 'Profile did not become active before timeout.'
            if current:
                msg += ' Current preset: ' + current
            outcome = 'failed'
        else:
            msg = 'Switch was requested, but its final state could not be verified.'
            if last and last['reason']:
                msg += ' ' + last['reason']
            outcome = 'unverified'
        log_event(outcome, index, msg)
        return emit(False, msg, slot=index, outcome=outcome,
                    verified=False, injector_state=state, backend=method)


def status():
    try:
        cfg = config()
        device, slots = slot_items(cfg)
    except RuntimeError as exc:
        return emit(False, str(exc), slots=[{'slot':i,'profile':'','label':f'Quick Preset {i}','loaded':False} for i in (1,2,3)])
    snap = live_snapshot(device)
    # A cached key can go stale after USB device reconnection. Refresh it if
    # the daemon seems to have no injection for this key and no state.
    if snap['group_source'] == 'cache' and not snap['preset'] and snap['state'] in ('UNKNOWN', 'UNAVAILABLE'):
        snap = live_snapshot(device, refresh_group=True)
    inferred = snap['detected'] and not snap['exact_available'] and injector_running(snap)
    hint = str(cfg.get('last_active_profile') or '') if inferred else ''
    for item in slots:
        item['active'] = confirmed_active(snap, item['profile']) or bool(hint and hint == item['profile'])
        item['active_estimated'] = bool(inferred and hint and hint == item['profile'])
    return emit(True, 'Quick Presets loaded.', slots=slots, device=device,
                detected=snap['detected'], resolved=snap['resolved'],
                exact_available=snap['exact_available'],
                confidence='state-only' if inferred else 'exact' if snap['exact_available'] else 'unknown',
                injector_state=snap['state'], group_key=snap['group_key'],
                running_preset=snap['preset'], reason=snap['reason'])


def launch():
    cmd = installed_command()
    if not cmd:
        return emit(False, 'Profile Switcher launcher not found. Open or install the main app first.')
    try:
        subprocess.Popen([cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        return emit(False, 'Could not launch Profile Switcher: ' + str(exc))
    return emit(True, 'Opening Profile Switcher.')


def doctor():
    report = {'config': str(CONFIG), 'config_found': CONFIG.is_file(),
              'profile_switcher': bool(installed_command()),
              'input_remapper': bool(which('input-remapper-control', 'SOLOPAW_WIDGET_CONTROL')),
              'busctl': bool(which('busctl', 'SOLOPAW_WIDGET_BUSCTL')),
              'native_cli': native_cli_supported()}
    try:
        cfg = config()
        device, slots = slot_items(cfg)
        snap = live_snapshot(device, refresh_group=True)
        report.update({'device': device, 'slots': slots,
                       'dbus_available': snap['detected'],
                       'group_resolved': snap['resolved'],
                       'group_key': snap['group_key'],
                       'exact_preset_supported': snap['exact_available'],
                       'injector_state': snap['state'],
                       'active': snap['preset'] if snap['detected'] else 'unknown',
                       'diagnostic': snap['reason']})
    except RuntimeError as exc:
        report['error'] = str(exc)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='soloPAW Quick Widget bridge')
    parser.add_argument('command', choices=['activate','status','launch','doctor'])
    parser.add_argument('slot', nargs='?', type=int, choices=[1,2,3])
    args = parser.parse_args(argv)
    if args.command == 'activate':
        if args.slot is None:
            parser.error('activate needs slot 1, 2, or 3')
        return activate(args.slot)
    if args.slot is not None:
        parser.error('slot only supported for activate')
    return {'status':status, 'launch':launch, 'doctor':doctor}[args.command]()


if __name__ == '__main__':
    raise SystemExit(main())
