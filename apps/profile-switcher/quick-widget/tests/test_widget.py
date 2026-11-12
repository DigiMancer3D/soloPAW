"""Run: python3 -m unittest discover -s tests -v"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODPATH = Path(__file__).resolve().parents[1] / 'helper/solopaw_widget_helper.py'
spec = importlib.util.spec_from_file_location('solopaw_widget_helper', MODPATH)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'app/config.json'
        self.config.parent.mkdir(parents=True)
        self.device = 'Logitech G502 HERO Gaming Mouse'
        self.presets = self.root / 'remap/presets' / self.device
        self.presets.mkdir(parents=True)
        for p in ['Cyberpunk', 'Megabonk', 'Desktop']:
            (self.presets / (p + '.json')).write_text('{}')
        self.appcfg = {'device': self.device, 'slots':[
            {'profile':'Cyberpunk','label':'CP 2077'},
            {'profile':'Megabonk','label':'MEGABONK!'},
            {'profile':'Desktop','label':'Linux Desktop'}
        ], 'common_names':{'Cyberpunk':'Cyber'}, 'some_future_new_setting': 234}
        self.config.write_text(json.dumps(self.appcfg))
        helper.CONFIG = self.config
        helper.ROOT = self.root / 'remap'
        helper.STATE_DIR = self.root / 'state'
        self.busstate = self.root / 'bus.json'
        self.busstate.write_text(json.dumps({'running':''}))
        self.busctl = self.root / 'fakebusctl'
        self.busctl.write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
if os.environ.get('MOCK_DBUS_DOWN')=='yes':
    sys.stderr.write('Service not reachable')
    sys.exit(2)
args=sys.argv
statefile=Path(os.environ['MOCK_STATE'])
state=json.loads(statefile.read_text())
name='Logitech G502 HERO Gaming Mouse'
key=name if os.environ.get('MOCK_LEGACY')=='yes' else os.environ.get('MOCK_GROUP_KEY','g502-unique-key')
if 'get_groups' in args:
    if os.environ.get('MOCK_GROUPS_DOWN')=='yes' or os.environ.get('MOCK_LEGACY')=='yes':
        sys.stderr.write('UnknownMethod get_groups')
        sys.exit(5)
    groups=[{'key':key,'names':[name,'Logitech G502 HERO Consumer Control'],'paths':['/dev/input/event42'],'types':['mouse']}]
    if os.environ.get('MOCK_GROUP_MISSING')=='yes':
        groups=[{'key':'other','names':['Other Mouse'],'paths':[],'types':['mouse']}]
    print('s '+json.dumps(json.dumps([json.dumps(g) for g in groups])))
    sys.exit(0)
if 'get_running_preset' in args:
    if os.environ.get('MOCK_LEGACY')=='yes':
        sys.stderr.write('UnknownMethod get_running_preset')
        sys.exit(5)
    print('s '+json.dumps(state['running'] if args[-1]==key else ''))
    sys.exit(0)
if 'get_state' in args:
    if args[-1]!=key:
        print('s "UNKNOWN"')
        sys.exit(0)
    current=state.get('injector_state', 'RUNNING' if state['running'] else 'STOPPED')
    if current=='STARTING':
        state['checks']=state.get('checks',0)+1
        if state['checks']>=3:
            state['injector_state']='RUNNING'
            current='RUNNING'
        statefile.write_text(json.dumps(state))
    print('s '+json.dumps(current))
    sys.exit(0)
sys.exit(5)
''')
        self.busctl.chmod(0o755)
        self.control = self.root / 'fakectrl'
        self.control.write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
args=sys.argv
if '--command' in args and args[args.index('--command')+1]=='hello':
    sys.exit(3 if os.environ.get('MOCK_HELLO_DOWN')=='yes' else 0)
if '--command' in args and args[args.index('--command')+1]=='start':
    if os.environ.get('MOCK_REJECT')=='yes':
        sys.exit(8)
    if os.environ.get('MOCK_START_NO_EFFECT')=='yes':
        sys.exit(0)
    preset=args[args.index('--preset')+1]
    state={'running':preset}
    if os.environ.get('MOCK_ASYNC')=='yes': state['injector_state']='STARTING'
    if os.environ.get('MOCK_INJECTOR_FAILED')=='yes': state['injector_state']='FAILED'
    Path(os.environ['MOCK_STATE']).write_text(json.dumps(state))
    sys.exit(0)
sys.exit(5)
''')
        self.control.chmod(0o755)
        env = {'SOLOPAW_WIDGET_BUSCTL':str(self.busctl),
               'SOLOPAW_WIDGET_CONTROL':str(self.control),
               'MOCK_STATE':str(self.busstate)}
        self.envpatch = patch.dict(os.environ, env, clear=False)
        self.envpatch.start()
        self.addCleanup(self.envpatch.stop)

    def output(self, fn, *args, **kwargs):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            rc=fn(*args,**kwargs)
        return rc,json.loads(stream.getvalue())

    def test_three_slots_and_names(self):
        rc, result=self.output(helper.status)
        self.assertEqual(rc,0)
        self.assertEqual([s['label'] for s in result['slots']],['CP 2077','MEGABONK!','Linux Desktop'])
        self.assertTrue(all(s['loaded'] for s in result['slots']))
        self.assertEqual([s['active'] for s in result['slots']],[False,False,False])

    def test_activate_verifies_actual_dbus_preset(self):
        rc, result=self.output(helper.activate,2,wait_seconds=0.2)
        self.assertEqual(rc,0)
        self.assertTrue(result['verified'])
        self.assertEqual(result['outcome'], 'verified')
        self.assertEqual(result['profile'],'Megabonk')
        self.assertEqual(json.loads(self.busstate.read_text())['running'],'Megabonk')
        self.assertEqual(json.loads((self.root/'state/device-key.json').read_text())['group_key'],'g502-unique-key')
        after=json.loads(self.config.read_text())
        self.assertEqual(after['some_future_new_setting'],234)
        self.assertEqual(after['slots'],self.appcfg['slots'])
        self.assertEqual(after['last_active_profile'],'Megabonk')

    def test_daemon_rejection_is_failure(self):
        with patch.dict(os.environ, {'MOCK_REJECT':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=0.2)
        self.assertEqual(rc,1)
        self.assertFalse(result['ok'])
        self.assertEqual(json.loads(self.busstate.read_text())['running'],'')

    def test_command_success_without_actual_switch_is_failure(self):
        with patch.dict(os.environ, {'MOCK_START_NO_EFFECT':'yes'}):
            rc,result=self.output(helper.activate,1,wait_seconds=0.05)
        self.assertEqual(rc,1)
        self.assertIn('did not become active',result['message'])
        self.assertEqual(result['outcome'], 'failed')
        self.assertNotIn('last_active_profile',json.loads(self.config.read_text()))

    def test_dbus_unavailable_means_not_verified(self):
        with patch.dict(os.environ, {'MOCK_DBUS_DOWN':'yes'}):
            rc,result=self.output(helper.activate,1,wait_seconds=0.05)
        self.assertEqual(rc,1)
        self.assertEqual(result['outcome'], 'unverified')
        self.assertIn('could not be verified',result['message'])

    def test_unassigned_slot(self):
        cfg=json.loads(self.config.read_text())
        cfg['slots'][2]['profile']=''
        self.config.write_text(json.dumps(cfg))
        rc,result=self.output(helper.activate,3,wait_seconds=0.05)
        self.assertEqual(rc,1)
        self.assertIn('empty',result['message'])

    def test_missing_profile(self):
        (self.presets / 'Desktop.json').unlink()
        rc,result=self.output(helper.activate,3,wait_seconds=0.05)
        self.assertEqual(rc,1)
        self.assertIn('missing',result['message'])

    def test_invalid_traversal_profile_is_not_loaded(self):
        cfg=json.loads(self.config.read_text())
        cfg['slots'][0]['profile']='../bad'
        self.config.write_text(json.dumps(cfg))
        rc,result=self.output(helper.status)
        self.assertEqual(rc,0)
        self.assertFalse(result['slots'][0]['loaded'])

    def test_retries_can_succeed(self):
        with patch.dict(os.environ, {'MOCK_REJECT':'yes'}):
            rc,result=self.output(helper.activate,1,wait_seconds=0.05)
        self.assertEqual(rc,1)
        rc,result=self.output(helper.activate,1,wait_seconds=0.05)
        self.assertEqual(rc,0)
        self.assertTrue(result['verified'])

    def test_doctor(self):
        rc,report=self.output(helper.doctor)
        self.assertEqual(rc,0)
        self.assertTrue(report['config_found'])
        self.assertTrue(report['dbus_available'])
        self.assertEqual(report['group_key'], 'g502-unique-key')
        self.assertTrue(report['group_resolved'])

    def test_external_switch_visible_in_status(self):
        self.busstate.write_text(json.dumps({'running':'Desktop','injector_state':'RUNNING'}))
        rc, report=self.output(helper.status)
        self.assertEqual(rc,0)
        self.assertEqual([s['active'] for s in report['slots']], [False,False,True])
        self.assertEqual(report['group_key'],'g502-unique-key')
        self.assertEqual(report['injector_state'],'RUNNING')

    def test_delayed_injector_waits_for_running(self):
        with patch.dict(os.environ, {'MOCK_ASYNC':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=12.0)
        self.assertEqual(rc,0)
        self.assertTrue(result['verified'])
        state=json.loads(self.busstate.read_text())
        self.assertEqual(state['injector_state'],'RUNNING')
        self.assertGreaterEqual(state['checks'],3)

    def test_failed_injector_after_cli_success_is_red_failure(self):
        with patch.dict(os.environ, {'MOCK_INJECTOR_FAILED':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=0.1)
        self.assertEqual(rc,1)
        self.assertEqual(result['outcome'],'failed')
        self.assertIn('FAILED',result['message'])

    def test_missing_group_is_not_marked_success(self):
        with patch.dict(os.environ, {'MOCK_GROUP_MISSING':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=0.1)
        self.assertEqual(rc,1)
        self.assertEqual(result['outcome'],'unverified')
        self.assertFalse(result['verified'])

    def test_unknown_group_discovery_is_never_false_success(self):
        with patch.dict(os.environ, {'MOCK_GROUPS_DOWN':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=0.1)
        self.assertEqual(rc,1)
        self.assertEqual(result['outcome'],'unverified')

    def test_bus_method_accepts_empty_running_preset(self):
        ok,value=helper.bus_method('get_running_preset','g502-unique-key')
        self.assertTrue(ok)
        self.assertEqual(value,'')

    def test_device_group_dump_can_be_json_string_array(self):
        entries=[{'key':'g502-unique-key','names':[self.device],'paths':[]}]
        encoded=json.dumps([json.dumps(e) for e in entries])
        self.assertEqual(helper.group_entries(encoded), entries)

    def test_input_remapper_221_state_only_applies_without_false_failure(self):
        with patch.dict(os.environ, {'MOCK_LEGACY':'yes'}):
            rc, result=self.output(helper.activate,1,wait_seconds=0.5)
            self.assertEqual(rc,0)
            self.assertEqual(result['outcome'],'applied')
            self.assertFalse(result['verified'])
            self.assertEqual(result['confidence'],'state-only')
            rc, state=self.output(helper.status)
            self.assertEqual(rc,0)
            self.assertEqual(state['confidence'],'state-only')
            self.assertEqual([s['active'] for s in state['slots']], [True,False,False])
            self.assertTrue(state['slots'][0]['active_estimated'])
            rc, report=self.output(helper.doctor)
            self.assertEqual(rc,0)
            self.assertFalse(report['exact_preset_supported'])
            self.assertEqual(report['injector_state'],'RUNNING')

    def test_input_remapper_221_injector_failed_still_fails(self):
        with patch.dict(os.environ, {'MOCK_LEGACY':'yes','MOCK_INJECTOR_FAILED':'yes'}):
            rc, result=self.output(helper.activate,2,wait_seconds=0.2)
        self.assertEqual(rc,1)
        self.assertEqual(result['outcome'],'failed')

    def test_input_remapper_221_external_switch_uses_main_app_hint(self):
        cfg=json.loads(self.config.read_text())
        cfg['last_active_profile']='Desktop'
        self.config.write_text(json.dumps(cfg))
        self.busstate.write_text(json.dumps({'running':'Desktop','injector_state':'RUNNING'}))
        with patch.dict(os.environ, {'MOCK_LEGACY':'yes'}):
            rc, result=self.output(helper.status)
        self.assertEqual(rc,0)
        self.assertTrue(result['slots'][2]['active'])
        self.assertTrue(result['slots'][2]['active_estimated'])
        self.assertEqual(result['confidence'],'state-only')



class StaticWidgetChecks(unittest.TestCase):
    def test_plasmoid_manifest_is_plasma6(self):
        root = Path(__file__).resolve().parents[1]
        meta = json.loads((root / 'widget/metadata.json').read_text())
        self.assertEqual(meta['KPackageStructure'], 'Plasma/Applet')
        self.assertEqual(meta['X-Plasma-API-Minimum-Version'], '6.0')
        self.assertEqual(meta['KPlugin']['Version'], '0.1.4')
        self.assertTrue((root / 'widget/contents/ui/main.qml').is_file())

    def test_button_icons_are_valid_png_assets(self):
        root = Path(__file__).resolve().parents[1]
        for name in ['logo.png', 'slot1.png', 'slot2.png', 'slot3.png']:
            path = root / 'widget/contents/images' / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_panel_reserves_space_in_both_orientations(self):
        root = Path(__file__).resolve().parents[1]
        qml = (root/'widget/contents/ui/main.qml').read_text()
        for expr in ["Layout.minimumHeight: implicitHeight", "Layout.minimumWidth: implicitWidth",
                     "Layout.preferredHeight: implicitHeight", "Layout.preferredWidth: implicitWidth",
                     "rows: root.verticalPanel ? 3 : 1", "columns: root.verticalPanel ? 1 : 3",
                     "Plasmoid.location === PlasmaCore.Types.RightEdge"]:
            self.assertIn(expr,qml)

    def test_image_fallback_and_icon_theme(self):
        root = Path(__file__).resolve().parents[1]
        orb = (root/'widget/contents/ui/QuickOrb.qml').read_text()
        self.assertIn('emblem.status !== Image.Ready',orb)
        meta = json.loads((root/'widget/metadata.json').read_text())
        self.assertEqual(meta['KPlugin']['Icon'], 'solopaw-quick-switch')
        self.assertTrue((root/'icon-theme/hicolor/128x128/apps/solopaw-quick-switch.png').is_file())
        self.assertIn('gtk-update-icon-cache',(root/'install.sh').read_text())
        self.assertTrue((root/'refresh-panel.sh').is_file())

    def test_live_verification_and_refresh_states(self):
        root=Path(__file__).resolve().parents[1]
        qml=(root/'widget/contents/ui/main.qml').read_text()
        orb=(root/'widget/contents/ui/QuickOrb.qml').read_text()
        for required in ['parsed.verified === true','parsed.outcome === "verified"',
                         'const uncertain','onTriggered:', 'externalStatusTimer',
                         'injector_state', 'root.setState(active, "idle")']:
            self.assertIn(required,qml)
        self.assertIn('orb.actionState === "unverified"',orb)
        self.assertIn('orb.actionState === "failed"',orb)
        self.assertIn('parsed.outcome === "applied"',qml)
        self.assertIn('activeConfidence',qml)

    def test_widget_has_all_required_gestures_and_feedback(self):
        root = Path(__file__).resolve().parents[1]
        qml = (root / 'widget/contents/ui/main.qml').read_text()
        orb = (root / 'widget/contents/ui/QuickOrb.qml').read_text()
        for required in ['onDoubleClicked', 'onClicked', 'singleRequested', 'appRequested']:
            self.assertIn(required, orb)
        for disabled in ['onPressAndHold', 'pressAndHoldInterval', 'drawerRequested', 'orb.held', 'hold: drawer']:
            self.assertNotIn(disabled, orb + qml)
        self.assertIn('interval: 12000', qml)
        for required in ['activate', 'failed', 'busy', 'verticalPanel', 'Plasmoid.formFactor']:
            self.assertIn(required, qml)
        self.assertIn('get_running_preset', (root / 'helper/solopaw_widget_helper.py').read_text())


if __name__ == '__main__':
    unittest.main()
