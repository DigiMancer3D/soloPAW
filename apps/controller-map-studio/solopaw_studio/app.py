from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any, Callable, Dict, Optional, Tuple

from PIL import ImageTk

from .core import (
    APP_NAME,
    DEFAULT_THEME,
    GESTURES,
    LAYERS,
    add_asset,
    add_card,
    asset_to_image,
    count_binding_links,
    accept_dependency_current,
    add_remapper_dependency,
    apply_dependency_update,
    binding_key_to_symbol,
    dependency_counts,
    dependency_diagnostics,
    dependency_state,
    describe_macro,
    encode_asset,
    ensure_card_content,
    ensure_card_fits_content,
    ensure_extension,
    ensure_remapper_metadata,
    export_binding_table,
    export_bundle,
    export_png,
    export_remapper,
    find_asset,
    find_binding_by_id,
    find_mapping_by_id,
    import_binding_table,
    load_project,
    make_binding_token,
    mapping_input_label,
    new_project,
    reconcile_binding_ids,
    render_project,
    save_project,
    sync_card_legacy_text,
    sync_card_z_indices,
    extract_macro_symbols,
    validate_macro_expression,
)


BG = "#090708"
PANEL = "#0d090a"
ENTRY = "#181113"
RED = "#ff5a52"
GREEN = "#8bd43f"
CYAN = "#26d7ed"
TEXT = "#eee9e7"


class VerticalScrolledFrame(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, bg=kwargs.get("bg", PANEL), highlightthickness=0, width=1)
        self.scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=kwargs.get("bg", PANEL))
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._configure)
        self.canvas.bind("<Configure>", self._canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")
        self.canvas.bind_all("<Button-4>", self._wheel_linux, add="+")
        self.canvas.bind_all("<Button-5>", self._wheel_linux, add="+")

    def _configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_configure(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def _wheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) and self._contains_pointer(event.x_root, event.y_root):
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _wheel_linux(self, event):
        if self._contains_pointer(event.x_root, event.y_root):
            self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    def _contains_pointer(self, x_root: int, y_root: int) -> bool:
        w = self.winfo_containing(x_root, y_root)
        while w is not None:
            if w == self:
                return True
            try:
                w = w.master
            except Exception:
                break
        return False


class BindingDialog(tk.Toplevel):
    COLUMNS = ("section", "action", "primary", "secondary", "context", "notes")

    def __init__(self, master, project: Dict[str, Any], on_change: Optional[Callable[[Optional[Dict[str, Any]]], None]] = None):
        super().__init__(master)
        self.title("Binding Table // Linked Map Intelligence")
        self.geometry("1240x680")
        self.minsize(920, 520)
        self.project = project
        self.on_change = on_change
        self.configure(bg="#0b0809")
        self.transient(master)

        style = ttk.Style(self)
        style.configure("Bindings.Treeview", background="#120d0f", fieldbackground="#120d0f", foreground="#eee", rowheight=27)
        style.configure("Bindings.Treeview.Heading", background="#2b1317", foreground="#ff6a61")
        style.map("Bindings.Treeview", background=[("selected", "#243f44")])

        header = tk.Frame(self, bg="#0b0809")
        header.pack(fill="x", padx=12, pady=10)
        tk.Label(header, text="CYBERPUNK-STYLE BINDING TABLE", fg=RED, bg="#0b0809", font=("Sans", 16, "bold")).pack(side="left")
        self.link_label = tk.Label(header, text="", fg=GREEN, bg="#0b0809")
        self.link_label.pack(side="left", padx=16)
        tk.Button(header, text="Refresh from Character Map", command=self.import_rows).pack(side="right", padx=4)
        tk.Button(header, text="Export Binding Table", command=self.export_rows).pack(side="right", padx=4)

        filterbar = tk.Frame(self, bg="#0b0809")
        filterbar.pack(fill="x", padx=12, pady=(0, 7))
        tk.Label(filterbar, text="Filter", fg=CYAN, bg="#0b0809").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.refresh())
        tk.Entry(filterbar, textvariable=self.filter_var, bg=ENTRY, fg=TEXT, insertbackground="#fff").pack(side="left", fill="x", expand=True, padx=(8, 0))

        frame = tk.Frame(self, bg="#0b0809")
        frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(frame, columns=self.COLUMNS, show="headings", selectmode="browse", style="Bindings.Treeview")
        widths = {"section": 165, "action": 300, "primary": 115, "secondary": 115, "context": 190, "notes": 280}
        for col in self.COLUMNS:
            self.tree.heading(col, text=col.replace("_", " ").title())
            self.tree.column(col, width=widths[col], anchor="w")
        ybar = tk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ybar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.edit_selected)

        controls = tk.Frame(self, bg="#0b0809")
        controls.pack(fill="x", padx=12, pady=10)
        tk.Button(controls, text="Add Row", command=self.add_row).pack(side="left", padx=4)
        tk.Button(controls, text="Edit Row", command=self.edit_selected).pack(side="left", padx=4)
        tk.Button(controls, text="Delete Row", command=self.delete_selected).pack(side="left", padx=4)
        tk.Label(controls, text="Linked {{key:Section::Action}} fields redraw immediately when a key changes.", fg=CYAN, bg="#0b0809").pack(side="right")
        self.refresh()

    def _changed(self, change: Optional[Dict[str, Any]] = None):
        self.refresh()
        if self.on_change:
            self.on_change(change)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        needle = self.filter_var.get().strip().casefold() if hasattr(self, "filter_var") else ""
        for idx, row in enumerate(self.project.get("bindings", [])):
            values = [row.get(c, "") for c in self.COLUMNS]
            if needle and needle not in " ".join(map(str, values)).casefold():
                continue
            self.tree.insert("", "end", iid=str(idx), values=values)
        self.link_label.configure(text=f"{count_binding_links(self.project)} live visual links")

    def _row_dialog(self, initial=None):
        initial = initial or {}
        win = tk.Toplevel(self)
        win.title("Binding")
        win.configure(bg=PANEL)
        win.transient(self)
        win.grab_set()
        vars_: Dict[str, tk.StringVar] = {}
        for r, col in enumerate(self.COLUMNS):
            tk.Label(win, text=col.replace("_", " ").title(), fg=TEXT, bg=PANEL).grid(row=r, column=0, sticky="e", padx=8, pady=5)
            v = tk.StringVar(value=initial.get(col, "")); vars_[col] = v
            tk.Entry(win, textvariable=v, width=58, bg=ENTRY, fg=TEXT, insertbackground="#fff").grid(row=r, column=1, padx=8, pady=5)
        result = {"value": None}
        def ok():
            row = {c: vars_[c].get().strip() for c in self.COLUMNS}
            if initial.get("id"):
                row["id"] = initial["id"]
            result["value"] = row
            win.destroy()
        tk.Button(win, text="Cancel", command=win.destroy).grid(row=len(self.COLUMNS), column=0, padx=8, pady=10)
        tk.Button(win, text="Save", command=ok).grid(row=len(self.COLUMNS), column=1, padx=8, pady=10, sticky="e")
        self.wait_window(win)
        return result["value"]

    def add_row(self):
        row = self._row_dialog()
        if row:
            row["id"] = str(uuid.uuid4())
            self.project.setdefault("bindings", []).append(row)
            self._changed({"type": "add", "new": deepcopy(row)})

    def edit_selected(self, *_):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        old_row = deepcopy(self.project["bindings"][idx])
        row = self._row_dialog(self.project["bindings"][idx])
        if row:
            self.project["bindings"][idx] = row
            self._changed({"type": "edit", "old": old_row, "new": deepcopy(row)})

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        row = self.project["bindings"][idx]
        if not messagebox.askyesno("Delete binding", f"Delete {row.get('section')} / {row.get('action')}?\n\nExisting visual links will show UNLINKED until relinked.", parent=self):
            return
        old_row = deepcopy(row)
        del self.project["bindings"][idx]
        self._changed({"type": "delete", "old": old_row})

    def import_rows(self):
        path = filedialog.askopenfilename(title="Refresh Character Map / Binding Table", filetypes=[("Binding data", "*.json *.csv"), ("All files", "*")])
        if not path:
            return
        try:
            rows = import_binding_table(path)
            replace = messagebox.askyesno(
                "Refresh Character Map",
                f"Read {len(rows)} rows. Replace the current binding table?\n\nMatching Section + Action rows preserve their internal link identity. Choose No to append.",
                parent=self,
            )
            if replace:
                self.project["bindings"] = reconcile_binding_ids(self.project.get("bindings", []), rows)
            else:
                self.project.setdefault("bindings", []).extend(rows)
            self._changed({"type": "import", "count": len(rows), "replace": replace})
        except Exception as e:
            messagebox.showerror("Import failed", str(e), parent=self)

    def export_rows(self):
        path = filedialog.asksaveasfilename(title="Export Binding Table", initialfile="Binding Table", defaultextension=".json", filetypes=[("Binding Table base", "*.json"), ("All files", "*")])
        if not path:
            return
        try:
            jp, cp = export_binding_table(path, self.project)
            messagebox.showinfo("Binding Table exported", f"Created:\n{jp}\n{cp}", parent=self)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self)


class DependencyDialog(tk.Toplevel):
    def __init__(self, master: "StudioApp", project: Dict[str, Any], on_change: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.app = master
        self.project = project
        self.on_change = on_change
        self.title("Remapper Dependency Diagnostics")
        self.geometry("1180x620")
        self.minsize(900, 460)
        self.configure(bg="#0b0809")
        ensure_remapper_metadata(project)

        header = tk.Frame(self, bg="#0b0809")
        header.pack(fill="x", padx=12, pady=10)
        tk.Label(header, text="BINDING ↔ REMAPPER DEPENDENCIES", fg=GREEN, bg="#0b0809", font=("Sans", 16, "bold")).pack(side="left")
        self.summary = tk.Label(header, text="", fg=CYAN, bg="#0b0809")
        self.summary.pack(side="left", padx=16)
        tk.Button(header, text="Open G502 Remapper", command=self.open_remapper).pack(side="right")

        frame = tk.Frame(self, bg="#0b0809")
        frame.pack(fill="both", expand=True, padx=12)
        cols = ("status", "input", "label", "current", "expected", "bindings")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = {"status":90, "input":100, "label":250, "current":100, "expected":110, "bindings":430}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("ok", foreground="#8bd43f")
        self.tree.tag_configure("kept", foreground="#26d7ed")
        self.tree.tag_configure("stale", foreground="#ffbd5c")
        self.tree.tag_configure("conflict", foreground="#ff5a52")
        self.tree.tag_configure("missing", foreground="#ff5a52")
        self.tree.tag_configure("unresolved", foreground="#bbb")
        y = tk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side="left", fill="both", expand=True); y.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.update_selected())

        controls = tk.Frame(self, bg="#0b0809")
        controls.pack(fill="x", padx=12, pady=10)
        tk.Button(controls, text="Refresh", command=self.refresh).pack(side="left", padx=3)
        tk.Button(controls, text="Update Selected Safely", command=self.update_selected).pack(side="left", padx=3)
        tk.Button(controls, text="Update All Safe", command=self.update_all).pack(side="left", padx=3)
        tk.Button(controls, text="Keep Current Selected", command=self.keep_selected).pack(side="left", padx=3)
        tk.Button(controls, text="Remove Link", command=self.remove_selected).pack(side="left", padx=3)
        tk.Label(controls, text="Conflicts are never auto-rewritten.", fg=CYAN, bg="#0b0809").pack(side="right")
        self.refresh()

    def _selected_dep(self):
        sel = self.tree.selection()
        if not sel:
            return None
        did = sel[0]
        return next((d for d in self.project.get("remapper_profile", {}).get("dependencies", []) if d.get("id") == did), None)

    def refresh(self):
        for iid in self.tree.get_children(): self.tree.delete(iid)
        diags = dependency_diagnostics(self.project)
        counts = dependency_counts(self.project)
        warn = sum(counts.get(k, 0) for k in ("stale", "conflict", "missing", "orphaned", "unresolved"))
        self.summary.configure(text=f"{len(diags)} links • {warn} need attention")
        for st in diags:
            bindings = "; ".join(f"{r.get('section')} / {r.get('action')}" for r in st["rows"])
            self.tree.insert("", "end", iid=str(st["id"]), values=(st["status"].upper(), st["mapping_input"], st["label"], st["current"], st["expected"], bindings), tags=(st["status"],))

    def _notify(self):
        self.refresh()
        if self.on_change: self.on_change()

    def update_selected(self):
        dep = self._selected_dep()
        if not dep: return
        try:
            apply_dependency_update(self.project, dep["id"])
            self._notify()
        except Exception as e:
            messagebox.showerror("Cannot safely update", str(e), parent=self)

    def update_all(self):
        updated = 0; skipped = []
        for dep in list(self.project.get("remapper_profile", {}).get("dependencies", [])):
            st = dependency_state(self.project, dep)
            if st["status"] in ("stale", "kept") and len(st["expected_symbols"]) == 1:
                try:
                    apply_dependency_update(self.project, dep["id"]); updated += 1
                except Exception as e:
                    skipped.append(str(e))
        self._notify()
        messagebox.showinfo("Dependency update", f"Safely updated {updated} linked macro key(s)." + (f"\nSkipped: {len(skipped)}" if skipped else ""), parent=self)

    def keep_selected(self):
        dep = self._selected_dep()
        if not dep: return
        try:
            accept_dependency_current(self.project, dep["id"]); self._notify()
        except Exception as e:
            messagebox.showerror("Cannot keep dependency", str(e), parent=self)

    def remove_selected(self):
        dep = self._selected_dep()
        if not dep: return
        if not messagebox.askyesno("Remove dependency", "Remove this Binding ↔ Remapper link?\n\nThe macro itself will not be changed.", parent=self): return
        did = dep["id"]
        self.project["remapper_profile"]["dependencies"] = [d for d in self.project["remapper_profile"]["dependencies"] if d.get("id") != did]
        self._notify()

    def open_remapper(self):
        RemapperDialog(self.app, self.project, on_change=self._notify)


class BindingImpactDialog(tk.Toplevel):
    def __init__(self, master: "StudioApp", change: Dict[str, Any], dep_ids: list[str]):
        super().__init__(master)
        self.app = master
        self.change = change
        self.dep_ids = dep_ids
        self.title("Binding Change Affects G502 Remapper")
        self.geometry("690x390")
        self.resizable(False, False)
        self.configure(bg="#0b0809")
        self.transient(master)
        old = change.get("old", {}); new = change.get("new", {})
        tk.Label(self, text="DEPENDENCY CHANGE DETECTED", fg=RED, bg="#0b0809", font=("Sans", 16, "bold")).pack(anchor="w", padx=18, pady=(16, 7))
        tk.Label(self, text=f"{new.get('section','')} / {new.get('action','')}", fg=TEXT, bg="#0b0809", font=("Sans", 12, "bold")).pack(anchor="w", padx=18)
        tk.Label(self, text=f"Binding: {old.get('primary','')}  →  {new.get('primary','')}", fg=CYAN, bg="#0b0809", font=("Sans", 12)).pack(anchor="w", padx=18, pady=(3, 12))
        rows = []
        for dep in master.project.get("remapper_profile", {}).get("dependencies", []):
            if dep.get("id") in dep_ids:
                st = dependency_state(master.project, dep)
                rows.append(f"• {st['label']}: remapper emits {st['current']} / binding expects {st['expected']} [{st['status']}]")
        msg = "Visual Map: updated ✓\nBinding Table: updated ✓\n\nRemapper Profile:\n" + "\n".join(rows)
        tk.Label(self, text=msg, justify="left", anchor="nw", wraplength=640, fg=TEXT, bg="#151012", padx=12, pady=12).pack(fill="both", expand=True, padx=18, pady=5)
        bar = tk.Frame(self, bg="#0b0809"); bar.pack(fill="x", padx=18, pady=14)
        tk.Button(bar, text="Update Safe Macro(s)", command=self.update_safe, bg="#21402a", fg="#fff").pack(side="left", padx=3)
        tk.Button(bar, text="Keep Remapper As-Is", command=self.keep, bg="#3a2e17", fg="#fff").pack(side="left", padx=3)
        tk.Button(bar, text="Inspect Dependencies", command=self.inspect, bg="#163039", fg="#fff").pack(side="right", padx=3)

    def update_safe(self):
        changed = 0
        for did in self.dep_ids:
            dep = next((d for d in self.app.project.get("remapper_profile", {}).get("dependencies", []) if d.get("id") == did), None)
            if not dep: continue
            st = dependency_state(self.app.project, dep)
            if st["status"] in ("stale", "kept") and len(st["expected_symbols"]) == 1:
                try: apply_dependency_update(self.app.project, did); changed += 1
                except Exception: pass
        self.app._dependency_changed()
        self.destroy()
        if changed == 0:
            messagebox.showinfo("No automatic rewrite", "No dependency was safe to rewrite. Open diagnostics to inspect conflicts.", parent=self.app)

    def keep(self):
        for did in self.dep_ids:
            try: accept_dependency_current(self.app.project, did)
            except Exception: pass
        self.app._dependency_changed(); self.destroy()

    def inspect(self):
        self.destroy(); self.app.open_dependencies()


class RemapperDialog(tk.Toplevel):
    """Structured remapper editor backed by the exact raw Input Remapper JSON."""
    def __init__(self, master: "StudioApp", project: Dict[str, Any], on_change: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.app = master
        self.project = project
        self.on_change = on_change
        ensure_remapper_metadata(project)
        self.title("G502 Remapper // Structured Macro Editor")
        self.geometry("1280x760")
        self.minsize(980, 600)
        self.configure(bg="#0b0809")
        self.selected_mapping_id: Optional[str] = None

        tk.Label(self, text="G502 REMAPPER // STRUCTURED MACRO EDITOR", fg=GREEN, bg="#0b0809", font=("Sans", 16, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(self, text="Raw Input Remapper JSON remains authoritative. Structured links add safe Binding Table dependency tracking without flattening timing/macros.", fg=CYAN, bg="#0b0809").pack(anchor="w", padx=12, pady=(0, 7))

        self.nb = ttk.Notebook(self); self.nb.pack(fill="both", expand=True, padx=10, pady=6)
        self.structured = tk.Frame(self.nb, bg="#0b0809"); self.raw = tk.Frame(self.nb, bg="#0b0809")
        self.nb.add(self.structured, text="Structured Mappings")
        self.nb.add(self.raw, text="Raw JSON")
        self._build_structured()
        self._build_raw()
        self.refresh_mappings()

    def _build_structured(self):
        pane = tk.PanedWindow(self.structured, orient="horizontal", sashwidth=6, bg="#0b0809")
        pane.pack(fill="both", expand=True)
        left = tk.Frame(pane, bg="#0b0809", width=510); right = tk.Frame(pane, bg=PANEL)
        pane.add(left, minsize=380); pane.add(right, minsize=440)

        cols = ("input", "target", "structure", "status")
        self.mapping_tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        widths = {"input":100, "target":130, "structure":190, "status":85}
        for c in cols:
            self.mapping_tree.heading(c, text=c.title()); self.mapping_tree.column(c, width=widths[c], anchor="w")
        y = tk.Scrollbar(left, orient="vertical", command=self.mapping_tree.yview); self.mapping_tree.configure(yscrollcommand=y.set)
        self.mapping_tree.pack(side="left", fill="both", expand=True, padx=(8,0), pady=8); y.pack(side="right", fill="y", pady=8)
        self.mapping_tree.bind("<<TreeviewSelect>>", lambda _e: self.populate_mapping())

        top = tk.Frame(right, bg=PANEL); top.pack(fill="x", padx=10, pady=(8,4))
        self.input_var = tk.StringVar(value="Select a mapping")
        tk.Label(top, textvariable=self.input_var, fg=CYAN, bg=PANEL, font=("Sans", 11, "bold")).pack(anchor="w")
        row = tk.Frame(right, bg=PANEL); row.pack(fill="x", padx=10, pady=4)
        tk.Label(row, text="Target", fg=TEXT, bg=PANEL).pack(side="left")
        self.target_var = tk.StringVar(value="keyboard")
        ttk.Combobox(row, textvariable=self.target_var, state="readonly", values=["keyboard", "mouse", "keyboard + mouse"]).pack(side="left", padx=8)
        self.structure_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self.structure_var, fg=GREEN, bg=PANEL, justify="left", anchor="w", wraplength=650).pack(fill="x", padx=10, pady=(2,5))
        tk.Label(right, text="Output / Macro", fg=RED, bg=PANEL, font=("Sans", 10, "bold")).pack(anchor="w", padx=10)
        self.output_text = tk.Text(right, height=5, bg=ENTRY, fg=TEXT, insertbackground="#fff", wrap="word", undo=True)
        self.output_text.pack(fill="x", padx=10, pady=4)
        brow = tk.Frame(right, bg=PANEL); brow.pack(fill="x", padx=10)
        tk.Button(brow, text="Validate", command=self.validate_selected).pack(side="left")
        tk.Button(brow, text="Gesture Builder…", command=self.open_gesture_builder).pack(side="left", padx=5)
        tk.Button(brow, text="Save Mapping", command=self.save_selected, bg="#301519", fg="#fff").pack(side="right")

        tk.Label(right, text="Detected Macro Symbols", fg=CYAN, bg=PANEL, font=("Sans", 10, "bold")).pack(anchor="w", padx=10, pady=(10,2))
        self.symbol_var = tk.StringVar()
        self.symbol_combo = ttk.Combobox(right, textvariable=self.symbol_var, state="readonly")
        self.symbol_combo.pack(fill="x", padx=10, pady=(0,5))

        depbox = tk.LabelFrame(right, text="Binding Dependencies", fg=GREEN, bg=PANEL)
        depbox.pack(fill="both", expand=True, padx=10, pady=6)
        cols = ("label", "current", "expected", "status")
        self.dep_tree = ttk.Treeview(depbox, columns=cols, show="headings", height=6, selectmode="browse")
        widths = {"label":310, "current":85, "expected":95, "status":90}
        for c in cols:
            self.dep_tree.heading(c, text=c.title()); self.dep_tree.column(c, width=widths[c], anchor="w")
        self.dep_tree.pack(fill="both", expand=True, padx=5, pady=5)
        link = tk.Frame(depbox, bg=PANEL); link.pack(fill="x", padx=5, pady=(0,5))
        self.binding_link_var = tk.StringVar()
        self.binding_link_combo = ttk.Combobox(link, textvariable=self.binding_link_var, state="readonly")
        self.binding_link_combo.pack(side="left", fill="x", expand=True)
        self.binding_field_var = tk.StringVar(value="primary")
        ttk.Combobox(link, textvariable=self.binding_field_var, state="readonly", values=["primary", "secondary"], width=10).pack(side="left", padx=4)
        tk.Button(link, text="Link Symbol", command=self.add_link).pack(side="left", padx=2)
        buttons = tk.Frame(depbox, bg=PANEL); buttons.pack(fill="x", padx=5, pady=(0,5))
        tk.Button(buttons, text="Auto-link Exact Primary Keys", command=self.auto_link).pack(side="left", padx=2)
        tk.Button(buttons, text="Update Safe", command=self.update_dep).pack(side="left", padx=2)
        tk.Button(buttons, text="Keep Current", command=self.keep_dep).pack(side="left", padx=2)
        tk.Button(buttons, text="Remove Link", command=self.remove_dep).pack(side="right", padx=2)

    def _build_raw(self):
        tk.Label(self.raw, text="Exact Input Remapper-compatible JSON. Studio-only IDs/dependencies are stripped when exporting G502 Remapper.json.", fg=CYAN, bg="#0b0809").pack(anchor="w", padx=10, pady=(10,2))
        self.raw_text = tk.Text(self.raw, bg="#111", fg="#eee", insertbackground="#fff", wrap="none")
        self.raw_text.pack(fill="both", expand=True, padx=10, pady=8)
        bar = tk.Frame(self.raw, bg="#0b0809"); bar.pack(fill="x", padx=10, pady=(0,10))
        tk.Button(bar, text="Import Profile JSON", command=self.import_profile).pack(side="left")
        tk.Button(bar, text="Reload From Project", command=self.reload_raw).pack(side="left", padx=4)
        tk.Button(bar, text="Validate + Apply Raw JSON", command=self.apply_raw).pack(side="right")
        self.reload_raw()

    def _mapping(self):
        return find_mapping_by_id(self.project, self.selected_mapping_id or "")

    def _mapping_status(self, mapping_id: str) -> str:
        statuses = [d["status"] for d in dependency_diagnostics(self.project) if d["mapping"] and d["mapping"].get("_studio_id") == mapping_id]
        order = ["conflict", "missing", "orphaned", "stale", "unresolved", "kept", "ok"]
        return next((s for s in order if s in statuses), "unlinked")

    def refresh_mappings(self):
        ensure_remapper_metadata(self.project)
        for iid in self.mapping_tree.get_children(): self.mapping_tree.delete(iid)
        for m in self.project["remapper_profile"]["mappings"]:
            mid = m["_studio_id"]
            summary = ", ".join(describe_macro(m.get("output_symbol", ""))[:2])
            self.mapping_tree.insert("", "end", iid=mid, values=(mapping_input_label(m), m.get("target_uinput", ""), summary, self._mapping_status(mid)))
        choices = [f"{r.get('section','')} :: {r.get('action','')}" for r in self.project.get("bindings", [])]
        self.binding_link_combo.configure(values=choices)
        if choices and self.binding_link_var.get() not in choices: self.binding_link_var.set(choices[0])
        self.reload_raw()
        if self.selected_mapping_id and self.mapping_tree.exists(self.selected_mapping_id):
            self.mapping_tree.selection_set(self.selected_mapping_id); self.populate_mapping()

    def populate_mapping(self):
        sel = self.mapping_tree.selection()
        if sel: self.selected_mapping_id = sel[0]
        m = self._mapping()
        if not m: return
        self.input_var.set("Input: " + mapping_input_label(m))
        self.target_var.set(m.get("target_uinput", "keyboard"))
        self.output_text.delete("1.0", "end"); self.output_text.insert("1.0", m.get("output_symbol", ""))
        self.structure_var.set(" • ".join(describe_macro(m.get("output_symbol", ""))))
        symbols = extract_macro_symbols(m.get("output_symbol", ""))
        self.symbol_combo.configure(values=symbols)
        if symbols: self.symbol_var.set(symbols[0])
        for iid in self.dep_tree.get_children(): self.dep_tree.delete(iid)
        for dep in self.project["remapper_profile"]["dependencies"]:
            if dep.get("mapping_id") != m.get("_studio_id"): continue
            st = dependency_state(self.project, dep)
            self.dep_tree.insert("", "end", iid=dep["id"], values=(st["label"], st["current"], st["expected"], st["status"].upper()))

    def validate_selected(self):
        ok, msg = validate_macro_expression(self.output_text.get("1.0", "end-1c"))
        (messagebox.showinfo if ok else messagebox.showerror)("Macro validation", msg + "\n\nInput Remapper remains the runtime authority.", parent=self)

    def save_selected(self):
        m = self._mapping()
        if not m: return
        text = self.output_text.get("1.0", "end-1c").strip()
        ok, msg = validate_macro_expression(text)
        if not ok:
            messagebox.showerror("Invalid macro", msg, parent=self); return
        m["target_uinput"] = self.target_var.get(); m["output_symbol"] = text
        self.refresh_mappings(); self._notify()

    def open_gesture_builder(self):
        m = self._mapping()
        if not m:
            messagebox.showinfo("Gesture Builder", "Select a G502 mapping first.", parent=self)
            return
        GestureMacroBuilderDialog(self, m, on_apply=self._builder_applied)

    def _builder_applied(self, expression: str):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", expression)
        self.save_selected()

    def _selected_dep(self):
        sel = self.dep_tree.selection()
        if not sel: return None
        did = sel[0]
        return next((d for d in self.project["remapper_profile"]["dependencies"] if d.get("id") == did), None)

    def add_link(self):
        m = self._mapping(); symbol = self.symbol_var.get(); choice = self.binding_link_var.get()
        if not m or not symbol or " :: " not in choice: return
        section, action = choice.split(" :: ", 1)
        row = next((r for r in self.project.get("bindings", []) if r.get("section", "") == section and r.get("action", "") == action), None)
        if not row: return
        field = self.binding_field_var.get()
        existing = next((d for d in self.project["remapper_profile"]["dependencies"] if d.get("mapping_id") == m["_studio_id"] and d.get("symbol") == symbol and d.get("binding_field") == field), None)
        if existing:
            if row["id"] not in existing["binding_ids"]: existing["binding_ids"].append(row["id"])
            actions = [find_binding_by_id(self.project, bid) for bid in existing["binding_ids"]]
            existing["label"] = " / ".join(r.get("action", "") for r in actions if r)
        else:
            add_remapper_dependency(self.project, m["_studio_id"], symbol, [row["id"]], binding_field=field, label=row.get("action", "Linked key"))
        self.populate_mapping(); self.refresh_mappings(); self._notify()

    def auto_link(self):
        m = self._mapping()
        if not m: return
        added = 0
        for symbol in extract_macro_symbols(m.get("output_symbol", "")):
            if any(d.get("mapping_id") == m["_studio_id"] and d.get("symbol") == symbol for d in self.project["remapper_profile"]["dependencies"]):
                continue
            rows = [r for r in self.project.get("bindings", []) if binding_key_to_symbol(r.get("primary", "")) == symbol]
            if not rows: continue
            label = " / ".join(r.get("action", "") for r in rows[:3]) + ("…" if len(rows) > 3 else "")
            add_remapper_dependency(self.project, m["_studio_id"], symbol, [r["id"] for r in rows], label=label)
            added += 1
        self.populate_mapping(); self.refresh_mappings(); self._notify()
        messagebox.showinfo("Auto-link", f"Created {added} exact-primary dependency link(s).\nReview grouped contextual bindings before relying on automatic updates.", parent=self)

    def update_dep(self):
        dep = self._selected_dep()
        if not dep: return
        try: apply_dependency_update(self.project, dep["id"]); self.populate_mapping(); self.refresh_mappings(); self._notify()
        except Exception as e: messagebox.showerror("Cannot safely update", str(e), parent=self)

    def keep_dep(self):
        dep = self._selected_dep()
        if not dep: return
        try: accept_dependency_current(self.project, dep["id"]); self.populate_mapping(); self.refresh_mappings(); self._notify()
        except Exception as e: messagebox.showerror("Cannot keep", str(e), parent=self)

    def remove_dep(self):
        dep = self._selected_dep()
        if not dep: return
        self.project["remapper_profile"]["dependencies"] = [d for d in self.project["remapper_profile"]["dependencies"] if d.get("id") != dep["id"]]
        self.populate_mapping(); self.refresh_mappings(); self._notify()

    def _preserve_ids(self, obj):
        old = self.project.get("remapper_profile", {}).get("mappings", [])
        def sig(m): return json.dumps(m.get("input_combination", []), sort_keys=True)
        by_sig = {sig(m): m.get("_studio_id") for m in old if m.get("_studio_id")}
        for m in obj:
            mid = by_sig.get(sig(m))
            if mid: m["_studio_id"] = mid
        return obj

    def import_profile(self):
        p = filedialog.askopenfilename(title="Import Input Remapper Profile", filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not p: return
        try:
            obj = json.loads(Path(p).read_text(encoding="utf-8"))
            if not isinstance(obj, list): raise ValueError("Input Remapper profile should be a JSON list")
            self.raw_text.delete("1.0", "end"); self.raw_text.insert("1.0", json.dumps(obj, indent=4))
        except Exception as e: messagebox.showerror("Import failed", str(e), parent=self)

    def reload_raw(self):
        if not hasattr(self, "raw_text"): return
        clean = [{k:v for k,v in m.items() if not str(k).startswith("_studio_")} for m in self.project.get("remapper_profile", {}).get("mappings", [])]
        self.raw_text.delete("1.0", "end"); self.raw_text.insert("1.0", json.dumps(clean, indent=4))

    def apply_raw(self):
        try:
            obj = json.loads(self.raw_text.get("1.0", "end"))
            if not isinstance(obj, list): raise ValueError("Profile must be a JSON list")
            obj = self._preserve_ids(obj)
            self.project.setdefault("remapper_profile", {})["mappings"] = obj
            ensure_remapper_metadata(self.project)
            self.selected_mapping_id = None
            self.refresh_mappings(); self._notify()
            messagebox.showinfo("Applied", f"Stored {len(obj)} remapper mappings. Existing dependency links were preserved where input identity still matched.", parent=self)
        except Exception as e: messagebox.showerror("Invalid remapper JSON", str(e), parent=self)

    def _notify(self):
        if self.on_change: self.on_change()


class GestureMacroBuilderDialog(tk.Toplevel):
    """Build common soloPAW Normal/G-Shift Tap/Double/Hold macros safely."""
    def __init__(self, master: RemapperDialog, mapping: Dict[str, Any], on_apply: Callable[[str], None]):
        super().__init__(master)
        self.mapping = mapping
        self.on_apply = on_apply
        self.title("Gesture Macro Builder")
        self.geometry("900x680")
        self.minsize(760, 560)
        self.configure(bg=PANEL)
        self.transient(master)
        tk.Label(self, text="GESTURE / MACRO BUILDER", fg=GREEN, bg=PANEL, font=("Sans", 15, "bold")).pack(anchor="w", padx=12, pady=(10,2))
        tk.Label(self, text="Plain key/button names generate key()/hold_keys().  Timed chains accept:  r -> e @ 1930.  Prefix expr: for an exact advanced expression.", fg=CYAN, bg=PANEL, wraplength=850, justify="left").pack(anchor="w", padx=12, pady=(0,6))
        cur = tk.Text(self, height=3, bg="#0b0809", fg=TEXT, wrap="word")
        cur.pack(fill="x", padx=12, pady=(0,8)); cur.insert("1.0", mapping.get("output_symbol", "")); cur.configure(state="disabled")

        body = tk.Frame(self, bg=PANEL); body.pack(fill="both", expand=True, padx=12)
        self.vars = {}
        self.shift_enabled = tk.BooleanVar(value="if_eq($soloPAW_shift" in mapping.get("output_symbol", ""))
        self.double_ms = tk.StringVar(value="300"); self.hold_ms = tk.StringVar(value="650")
        for col, layer in enumerate(("normal", "shift")):
            box = tk.LabelFrame(body, text="NORMAL" if layer == "normal" else "G-SHIFT", fg=RED if layer == "normal" else GREEN, bg=PANEL)
            box.grid(row=0, column=col, sticky="nsew", padx=(0,6) if col == 0 else (6,0), pady=4)
            if layer == "shift":
                tk.Checkbutton(box, text="Enable G-Shift branch", variable=self.shift_enabled, bg=PANEL, fg=TEXT, selectcolor="#222", activebackground=PANEL).grid(row=0,column=0,columnspan=2,sticky="w",padx=6,pady=4)
                start=1
            else: start=0
            for r, gesture in enumerate(("tap","double","hold"), start=start):
                label = {"tap":"Tap / primary", "double":"Double tap", "hold":"Hold gesture"}[gesture]
                tk.Label(box, text=label, fg=TEXT, bg=PANEL).grid(row=r,column=0,sticky="w",padx=6,pady=5)
                v=tk.StringVar(); self.vars[(layer,gesture)] = v
                tk.Entry(box, textvariable=v, bg=ENTRY, fg=TEXT, insertbackground="#fff").grid(row=r,column=1,sticky="ew",padx=6,pady=5)
            phys=tk.BooleanVar(value=False); self.vars[(layer,"physical")]=phys
            tk.Checkbutton(box, text="Primary follows physical press duration", variable=phys, bg=PANEL, fg=TEXT, selectcolor="#222", activebackground=PANEL).grid(row=start+3,column=0,columnspan=2,sticky="w",padx=6,pady=5)
            box.columnconfigure(1,weight=1)
        body.columnconfigure(0,weight=1); body.columnconfigure(1,weight=1); body.rowconfigure(0,weight=1)

        timing=tk.Frame(self,bg=PANEL); timing.pack(fill="x",padx=12,pady=6)
        tk.Label(timing,text="Double window ms",fg=TEXT,bg=PANEL).pack(side="left")
        tk.Entry(timing,textvariable=self.double_ms,width=6,bg=ENTRY,fg=TEXT,insertbackground="#fff").pack(side="left",padx=4)
        tk.Label(timing,text="Hold threshold ms",fg=TEXT,bg=PANEL).pack(side="left",padx=(12,0))
        tk.Entry(timing,textvariable=self.hold_ms,width=6,bg=ENTRY,fg=TEXT,insertbackground="#fff").pack(side="left",padx=4)

        self.preview_var=tk.StringVar(value="Fill fields, then Preview.")
        tk.Label(self,textvariable=self.preview_var,fg=CYAN,bg="#0b0809",anchor="w",justify="left",wraplength=850,padx=8,pady=8).pack(fill="x",padx=12,pady=5)
        bar=tk.Frame(self,bg=PANEL); bar.pack(fill="x",padx=12,pady=(2,10))
        tk.Button(bar,text="Preview",command=self.preview).pack(side="left")
        tk.Button(bar,text="Apply to Selected Mapping",command=self.apply,bg="#301519",fg="#fff").pack(side="right")

    @staticmethod
    def _symbol(value: str) -> str:
        v=value.strip()
        return binding_key_to_symbol(v) or v

    def _tap_expr(self, value: str, physical: bool=False) -> str:
        raw=value.strip()
        if not raw: return ""
        if raw.lower().startswith("expr:"): return raw[5:].strip()
        import re as _re
        m=_re.match(r"^(.+?)\s*->\s*(.+?)(?:\s*@\s*(\d+))?$", raw)
        if m:
            a=self._symbol(m.group(1)); b=self._symbol(m.group(2)); ms=int(m.group(3) or 1930)
            return f"key({a}).key_down({b}).wait({ms}).key_up({b})"
        sym=self._symbol(raw)
        return f"hold_keys({sym})" if physical else f"key({sym})"

    def _hold_expr(self, value: str) -> str:
        raw=value.strip()
        if not raw: return ""
        if raw.lower().startswith("expr:"): return raw[5:].strip()
        return f"hold_keys({self._symbol(raw)})"

    def _layer_expr(self, layer: str) -> str:
        tap=self._tap_expr(self.vars[(layer,"tap")].get(), bool(self.vars[(layer,"physical")].get()))
        double=self._tap_expr(self.vars[(layer,"double")].get(), False)
        hold=self._hold_expr(self.vars[(layer,"hold")].get())
        if not tap:
            raise ValueError(f"{layer.title()} Tap / primary is required")
        try: dms=max(80,int(self.double_ms.get())); hms=max(dms+50,int(self.hold_ms.get()))
        except Exception: raise ValueError("Timing values must be integers")
        expr=tap
        if double: expr=f"if_tap({double},{tap},{dms})"
        if hold: expr=f"if_tap({expr},{hold},{hms})"
        return expr

    def build(self) -> str:
        normal=self._layer_expr("normal")
        if self.shift_enabled.get():
            shift=self._layer_expr("shift")
            return f"if_eq($soloPAW_shift,1,{shift},{normal})"
        return normal

    def preview(self):
        try:
            expr=self.build(); ok,msg=validate_macro_expression(expr)
            self.preview_var.set(("✓ " if ok else "⚠ ")+expr+("" if ok else f"\n{msg}"))
        except Exception as e: self.preview_var.set(f"⚠ {e}")

    def apply(self):
        try:
            expr=self.build(); ok,msg=validate_macro_expression(expr)
            if not ok: raise ValueError(msg)
            self.on_apply(expr); self.destroy()
        except Exception as e: messagebox.showerror("Macro Builder", str(e), parent=self)


class IconLibraryDialog(tk.Toplevel):
    def __init__(self, master: "StudioApp"):
        super().__init__(master)
        self.app = master
        self.project = master.project
        self.title("Icon / SVG Library")
        self.geometry("760x520")
        self.minsize(620, 420)
        self.configure(bg=PANEL)
        self.preview_photo = None

        left = tk.Frame(self, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        tk.Label(left, text="ICON / SVG LIBRARY", fg=CYAN, bg=PANEL, font=("Sans", 14, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(left, bg=ENTRY, fg=TEXT, selectbackground="#26434a")
        self.listbox.pack(fill="both", expand=True, pady=8)
        self.listbox.bind("<<ListboxSelect>>", lambda _e: self.refresh_preview())
        buttons = tk.Frame(left, bg=PANEL); buttons.pack(fill="x")
        tk.Button(buttons, text="Import PNG/SVG", command=self.import_asset).pack(side="left")
        tk.Button(buttons, text="Remove Project Asset", command=self.remove_asset).pack(side="left", padx=5)

        right = tk.Frame(self, bg="#120d0f", width=260)
        right.pack(side="right", fill="y", padx=(0, 10), pady=10)
        tk.Label(right, text="CARD ICON", fg=RED, bg="#120d0f", font=("Sans", 12, "bold")).pack(anchor="w", padx=10, pady=(10, 3))
        self.preview = tk.Label(right, text="Select an icon", bg="#120d0f", fg=TEXT, width=24, height=10)
        self.preview.pack(padx=10, pady=8)
        tk.Label(right, text="Tint", fg=TEXT, bg="#120d0f").pack(anchor="w", padx=10)
        self.tint_var = tk.StringVar(value="normal")
        ttk.Combobox(right, textvariable=self.tint_var, values=["normal", "shift", "cyan", "original"], state="readonly").pack(fill="x", padx=10, pady=5)
        tk.Button(right, text="Assign to Selected Card", command=self.assign).pack(fill="x", padx=10, pady=(10, 4))
        tk.Button(right, text="Clear Card Icon", command=self.clear).pack(fill="x", padx=10, pady=4)
        tk.Label(right, text="Imported art is embedded in .udata.\nUse assets you are permitted to use.", fg=CYAN, bg="#120d0f", justify="left", wraplength=220).pack(anchor="w", padx=10, pady=12)
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, "end")
        for asset in self.project.get("asset_library", []):
            prefix = "[builtin] " if str(asset.get("id", "")).startswith("builtin:") else ""
            self.listbox.insert("end", prefix + str(asset.get("name", "unnamed")))

    def selected_asset(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.project.get("asset_library", [])[sel[0]]

    def refresh_preview(self):
        asset = self.selected_asset()
        if not asset:
            return
        im = asset_to_image(asset, (180, 180))
        if not im:
            self.preview.configure(text="Preview unavailable", image="")
            return
        self.preview_photo = ImageTk.PhotoImage(im)
        self.preview.configure(image=self.preview_photo, text="")

    def import_asset(self):
        p = filedialog.askopenfilename(title="Import icon", filetypes=[("Icon assets", "*.svg *.png *.webp *.jpg *.jpeg"), ("All files", "*")])
        if not p:
            return
        try:
            add_asset(self.project, p)
            self.app._set_dirty()
            self.refresh_list()
            self.listbox.selection_clear(0, "end"); self.listbox.selection_set("end")
            self.refresh_preview()
        except Exception as e:
            messagebox.showerror("Icon import failed", str(e), parent=self)

    def remove_asset(self):
        asset = self.selected_asset()
        if not asset or str(asset.get("id", "")).startswith("builtin:"):
            messagebox.showinfo("Icon Library", "Built-in icons are retained. Select an imported project asset to remove.", parent=self)
            return
        aid = asset.get("id")
        self.project["asset_library"] = [a for a in self.project.get("asset_library", []) if a.get("id") != aid]
        for c in self.project.get("cards", []):
            if c.get("icon_id") == aid:
                c["icon_id"] = None
        self.refresh_list(); self.app._set_dirty(); self.app.populate_properties(); self.app.refresh_preview()

    def assign(self):
        card = self.app.current_card(); asset = self.selected_asset()
        if not card:
            messagebox.showinfo("Icon Library", "Select a control card first.", parent=self); return
        if not asset:
            messagebox.showinfo("Icon Library", "Select an icon first.", parent=self); return
        card["icon_id"] = asset.get("id")
        card["icon_tint"] = self.tint_var.get()
        self.app._set_dirty(); self.app.populate_properties(); self.app.refresh_preview()

    def clear(self):
        card = self.app.current_card()
        if card:
            card["icon_id"] = None
            self.app._set_dirty(); self.app.populate_properties(); self.app.refresh_preview()


class StudioApp(tk.Tk):
    HANDLE_SIZE = 10
    MIN_CARD_W = 130
    MIN_CARD_H = 90
    MIN_TEXT_SIZE = 8
    MAX_TEXT_SIZE = 34

    def __init__(self, default_project: Optional[Path] = None, initial_project: Optional[Path] = None):
        super().__init__(className="Solopawcontrollermapstudio")
        self.geometry("1500x920")
        self.minsize(1050, 680)
        self.configure(bg=BG)
        self._app_icon_photo = None
        try:
            icon_path = Path(__file__).resolve().parents[1] / "assets" / "solopaw-controller-map-studio.png"
            if icon_path.exists():
                self._app_icon_photo = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, self._app_icon_photo)
        except Exception:
            pass
        self.default_project_path = default_project.resolve() if default_project else None
        self.initial_project_path = initial_project.resolve() if initial_project else None
        self.project_path: Optional[Path] = None
        self.project: Dict[str, Any] = new_project()
        self.dirty = False
        self.selected_card_id: Optional[str] = None
        self.selected_card_ids = set()
        self.selected_image_kind: Optional[str] = None
        self._interaction: Optional[str] = None
        self._interaction_changed = False
        self._drag_start: Optional[Tuple[float, float]] = None
        self._drag_card_start: Optional[Dict[str, int]] = None
        self._drag_multi_start: Dict[str, Tuple[int, int]] = {}
        self._drag_image_start: Optional[Dict[str, int]] = None
        self._preview_photo = None
        self._render_after = None
        self.active_content_text: Optional[tk.Text] = None
        self._context_popup: Optional[tk.Toplevel] = None
        self._context_kind: Optional[str] = None
        self._context_target: Optional[str] = None
        self.ui_state_path = Path.home() / ".config" / "solopaw-controller-map-studio" / "ui.json"
        self.ui_state = self._load_ui_state()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if initial_project and initial_project.exists():
            self.open_path(initial_project, as_template=False)
        elif default_project and default_project.exists():
            self.open_path(default_project, as_template=True)
        else:
            self._ensure_builtin_icons(); self.refresh_binding_choices(); self.refresh_preview(); self._update_title()
        self.after(120, self._restore_pane_width)
        self._refresh_dependency_status()

    # ---------- UI state / dirty state ----------
    def _load_ui_state(self) -> Dict[str, Any]:
        defaults = {"inspector_visible": True, "inspector_width": 390, "image_select_open": False, "snap_enabled": True, "snap_size": 10}
        try:
            if self.ui_state_path.exists():
                loaded = json.loads(self.ui_state_path.read_text(encoding="utf-8"))
                defaults.update({k: v for k, v in loaded.items() if k in defaults})
        except Exception:
            pass
        return defaults

    def _save_ui_state(self):
        try:
            if self.inspector_visible and self.inspector_frame.winfo_ismapped():
                self.ui_state["inspector_width"] = max(220, self.inspector_frame.winfo_width())
            self.ui_state["inspector_visible"] = self.inspector_visible
            self.ui_state["image_select_open"] = bool(self.image_select_open)
            if hasattr(self, "snap_enabled_var"):
                self.ui_state["snap_enabled"] = bool(self.snap_enabled_var.get())
            if hasattr(self, "snap_size_var"):
                try: self.ui_state["snap_size"] = max(1, int(self.snap_size_var.get()))
                except Exception: pass
            self.ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            self.ui_state_path.write_text(json.dumps(self.ui_state, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _restore_pane_width(self):
        if not self.inspector_visible:
            self._hide_inspector(save=False)
            return
        try:
            total = self.body_pane.winfo_width()
            width = int(self.ui_state.get("inspector_width", 390))
            self.body_pane.sash_place(0, max(200, total - width), 1)
        except Exception:
            pass

    def _display_name(self) -> str:
        if self.project_path:
            return self.project_path.name
        return self.project.get("project", {}).get("name", "Untitled soloPAW Map") + " [template copy]"

    def _update_title(self):
        mark = " *" if self.dirty else ""
        self.title(f"{APP_NAME} — {self._display_name()}{mark}")

    def _set_dirty(self, dirty: bool = True):
        self.dirty = bool(dirty)
        self._update_title()

    def _confirm_discard(self, action: str) -> bool:
        if not self.dirty:
            return True
        choice = messagebox.askyesnocancel(
            "Unsaved edits",
            f"Save the current .udata before {action}?",
            parent=self,
        )
        if choice is None:
            return False
        if choice:
            return bool(self.save_project_cmd())
        return True

    def _on_close(self):
        if not self._confirm_discard("closing"):
            return
        self._save_ui_state()
        self._close_context_popup()
        self.destroy()

    # ---------- UI construction ----------
    def _build_ui(self):
        self.toolbar = tk.Frame(self, bg="#160b0d", bd=0, height=42)
        self.toolbar.pack(fill="x")
        for label, cmd in [
            ("New", self.new_project_cmd), ("Open .udata", self.open_project_cmd), ("Save .udata", self.save_project_cmd),
            ("Export PNG", self.export_png_cmd), ("Export Bundle", self.export_bundle_cmd), ("G502 Remapper", self.open_remapper), ("Binding Table", self.open_bindings),
            ("Dependencies", self.open_dependencies), ("Icon Library", self.open_icon_library), ("Add Card", self.add_card_cmd),
            ("Delete Card", self.delete_card_cmd), ("Image Select", self.toggle_image_select),
        ]:
            tk.Button(self.toolbar, text=label, command=cmd, bg="#241215", fg="#f4eded", activebackground="#3a191d", relief="flat", padx=8).pack(side="left", padx=2, pady=4)
        align = tk.Menubutton(self.toolbar, text="Align", bg="#241215", fg="#f4eded", activebackground="#3a191d", relief="flat", padx=8)
        am = tk.Menu(align, tearoff=0)
        for label, mode in [("Left", "left"), ("Right", "right"), ("Top", "top"), ("Bottom", "bottom"), ("Horizontal Centers", "hcenter"), ("Vertical Centers", "vcenter"), ("Distribute Horizontally", "distribute_h"), ("Distribute Vertically", "distribute_v")]:
            am.add_command(label=label, command=lambda m=mode: self.align_selected(m))
        align.configure(menu=am); align.pack(side="left", padx=2, pady=4)
        self.snap_enabled_var = tk.BooleanVar(value=bool(self.ui_state.get("snap_enabled", True)))
        self.snap_size_var = tk.StringVar(value=str(self.ui_state.get("snap_size", 10)))
        tk.Checkbutton(self.toolbar, text="Snap", variable=self.snap_enabled_var, command=self._save_ui_state, bg="#160b0d", fg=CYAN, selectcolor="#222", activebackground="#160b0d").pack(side="left", padx=(6,1))
        tk.Entry(self.toolbar, textvariable=self.snap_size_var, width=3, bg=ENTRY, fg=TEXT, insertbackground="#fff").pack(side="left", padx=(0,4), pady=6)
        self.inspector_toggle_var = tk.StringVar(value="Hide Inspector")
        tk.Button(self.toolbar, textvariable=self.inspector_toggle_var, command=self.toggle_inspector, bg="#163039", fg="#eafcff", relief="flat", padx=8).pack(side="right", padx=4, pady=4)
        self.dependency_status_var = tk.StringVar(value="Deps: 0")
        tk.Label(self.toolbar, textvariable=self.dependency_status_var, fg=GREEN, bg="#160b0d").pack(side="right", padx=8)
        tk.Label(self.toolbar, text="Shift-click = multi-select • Wheel = text size • cyan dots = midpoint/end", fg=CYAN, bg="#160b0d").pack(side="right", padx=8)

        self.image_select_frame = tk.Frame(self, bg="#11171a", bd=1, relief="solid")
        self._build_image_select_panel()
        self.image_select_open = False

        self.body_pane = tk.PanedWindow(self, orient="horizontal", sashwidth=7, sashrelief="flat", bg=BG)
        self.body_pane.pack(fill="both", expand=True)
        self.body_pane.bind("<ButtonRelease-1>", lambda _e: self._save_ui_state(), add="+")
        self.left_frame = tk.Frame(self.body_pane, bg=BG)
        self.inspector_frame = tk.Frame(self.body_pane, bg=PANEL, width=390)
        self.body_pane.add(self.left_frame, stretch="always")
        self.body_pane.add(self.inspector_frame, minsize=220)
        self.inspector_visible = True

        self.canvas = tk.Canvas(self.left_frame, bg="#070607", highlightthickness=0, xscrollincrement=1, yscrollincrement=1)
        xbar = tk.Scrollbar(self.left_frame, orient="horizontal", command=self.canvas.xview)
        ybar = tk.Scrollbar(self.left_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew"); ybar.grid(row=0, column=1, sticky="ns"); xbar.grid(row=1, column=0, sticky="ew")
        self.left_frame.rowconfigure(0, weight=1); self.left_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Control-Button-1>", self.set_anchor)
        self.canvas.bind("<B1-Motion>", self.canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.canvas_release)
        self.canvas.bind("<Button-3>", self.canvas_right_click)
        self.canvas.bind("<Double-Button-3>", self.canvas_double_right_click)
        self.canvas.bind("<MouseWheel>", self.canvas_mousewheel)
        self.canvas.bind("<Button-4>", self.canvas_mousewheel)
        self.canvas.bind("<Button-5>", self.canvas_mousewheel)

        header = tk.Frame(self.inspector_frame, bg="#160b0d")
        header.pack(fill="x")
        tk.Label(header, text="SELECTED CONTROL", fg=RED, bg="#160b0d", font=("Sans", 13, "bold")).pack(side="left", padx=10, pady=8)
        tk.Button(header, text="×", command=self.toggle_inspector, bg="#241215", fg=TEXT, relief="flat", width=3).pack(side="right", padx=4)

        self.scroller = VerticalScrolledFrame(self.inspector_frame, bg=PANEL)
        self.scroller.pack(fill="both", expand=True)
        self.inspector_body = self.scroller.inner
        self._build_inspector_fields()

        status = tk.Frame(self, bg="#120b0c")
        status.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status, textvariable=self.status_var, fg=CYAN, bg="#120b0c", anchor="w").pack(fill="x", padx=8, pady=3)

        self.image_select_open = bool(self.ui_state.get("image_select_open", False))
        if self.image_select_open:
            self.after(20, self._show_image_select)

    def _build_image_select_panel(self):
        head = tk.Frame(self.image_select_frame, bg="#11171a")
        head.pack(fill="x", padx=8, pady=(6, 3))
        tk.Label(head, text="IMAGE SELECT", fg=CYAN, bg="#11171a", font=("Sans", 11, "bold")).pack(side="left")
        tk.Label(head, text="Background and controller images are embedded into .udata", fg=TEXT, bg="#11171a").pack(side="left", padx=12)
        tk.Button(head, text="×", command=self.toggle_image_select, bg="#241215", fg=TEXT, relief="flat", width=3).pack(side="right")

        grid = tk.Frame(self.image_select_frame, bg="#11171a")
        grid.pack(fill="x", padx=8, pady=(0, 7))
        self.image_vars: Dict[str, tk.StringVar] = {}
        headers = ["Layer", "Current Asset", "X", "Y", "Width", "Height", "Actions"]
        for c, text in enumerate(headers):
            tk.Label(grid, text=text, fg=GREEN if c < 2 else CYAN, bg="#11171a", font=("Sans", 9, "bold")).grid(row=0, column=c, sticky="w", padx=3)
        for r, kind in enumerate(("background", "controller"), start=1):
            tk.Label(grid, text="Background" if kind == "background" else "Controller / Mouse", fg=TEXT, bg="#11171a").grid(row=r, column=0, sticky="w", padx=3, pady=3)
            asset_var = tk.StringVar(value="None"); self.image_vars[f"{kind}_asset"] = asset_var
            tk.Label(grid, textvariable=asset_var, fg=TEXT, bg="#11171a", anchor="w").grid(row=r, column=1, sticky="ew", padx=3)
            for c, key in enumerate(("x", "y", "width", "height"), start=2):
                v = tk.StringVar(); self.image_vars[f"{kind}_{key}"] = v
                tk.Entry(grid, textvariable=v, width=8, bg=ENTRY, fg=TEXT, insertbackground="#fff").grid(row=r, column=c, padx=2)
            buttons = tk.Frame(grid, bg="#11171a")
            buttons.grid(row=r, column=6, sticky="w")
            choose = self.choose_background_image if kind == "background" else self.choose_controller_image
            clear = self.clear_background_image if kind == "background" else self.clear_controller_image
            tk.Button(buttons, text="Choose…", command=choose).pack(side="left", padx=2)
            tk.Button(buttons, text="Clear", command=clear).pack(side="left", padx=2)
        grid.columnconfigure(1, weight=1)
        tk.Button(self.image_select_frame, text="Apply Image Geometry", command=self.apply_image_geometry, bg="#163039", fg="#fff", relief="flat").pack(anchor="e", padx=10, pady=(0, 7))

    def _build_inspector_fields(self):
        self.fields_container = tk.Frame(self.inspector_body, bg=PANEL)
        self.fields_container.pack(fill="both", expand=True)

        geo = tk.LabelFrame(self.fields_container, text="Geometry", bg=PANEL, fg=CYAN, bd=1)
        geo.pack(fill="x", padx=10, pady=(10, 5))
        self.vars: Dict[str, tk.StringVar] = {}
        fields = [
            ("title", "Title"), ("x", "X"), ("y", "Y"), ("width", "Width"), ("height", "Height"),
            ("text_size", "Text Size"), ("mid_x", "Line Mid X"), ("mid_y", "Line Mid Y"),
            ("anchor_x", "Line End X"), ("anchor_y", "Line End Y"),
        ]
        for row, (key, label) in enumerate(fields):
            tk.Label(geo, text=label, fg=TEXT, bg=PANEL).grid(row=row, column=0, sticky="w", pady=2, padx=(6, 4))
            v = tk.StringVar(); self.vars[key] = v
            e = tk.Entry(geo, textvariable=v, bg=ENTRY, fg=TEXT, insertbackground="#fff")
            e.grid(row=row, column=1, sticky="ew", pady=2, padx=(0, 6)); e.bind("<Return>", lambda _e: self.apply_properties())
        geo.columnconfigure(1, weight=1)
        tk.Label(geo, text="Tip: with a card selected, wheel up/down changes Text Size. The card grows only right/down if needed.", fg=GREEN, bg=PANEL, wraplength=330, justify="left").grid(row=len(fields), column=0, columnspan=2, sticky="w", padx=6, pady=5)

        author = tk.LabelFrame(self.fields_container, text="Structured Actions", bg=PANEL, fg=CYAN, bd=1)
        author.pack(fill="x", padx=10, pady=5)
        self.content_texts: Dict[Tuple[str, str], tk.Text] = {}
        notebook = ttk.Notebook(author)
        notebook.pack(fill="x", padx=5, pady=5)
        for layer in LAYERS:
            tab = tk.Frame(notebook, bg=PANEL)
            notebook.add(tab, text="Normal" if layer == "normal" else "G-Shift")
            for idx, gesture in enumerate(GESTURES):
                color = RED if layer == "normal" else GREEN
                tk.Label(tab, text=gesture.upper(), fg=color, bg=PANEL, font=("Sans", 9, "bold")).pack(anchor="w", padx=5, pady=(5 if idx == 0 else 3, 1))
                t = tk.Text(tab, height=3, bg=ENTRY, fg=TEXT, insertbackground="#fff", wrap="word", undo=True)
                t.pack(fill="x", padx=5)
                t.bind("<FocusIn>", lambda _e, widget=t: setattr(self, "active_content_text", widget))
                self.content_texts[(layer, gesture)] = t

        linkbar = tk.Frame(author, bg=PANEL)
        linkbar.pack(fill="x", padx=5, pady=(7, 6))
        self.binding_choice_var = tk.StringVar()
        self.binding_combo = ttk.Combobox(linkbar, textvariable=self.binding_choice_var, state="readonly")
        self.binding_combo.pack(side="left", fill="x", expand=True)
        tk.Button(linkbar, text="Insert Key Link", command=lambda: self.insert_binding_link("key")).pack(side="left", padx=3)
        tk.Button(linkbar, text="Insert Action", command=lambda: self.insert_binding_link("action")).pack(side="left")
        tk.Label(author, text="Linked tokens resolve from Binding Table at render/export time.", fg=GREEN, bg=PANEL).pack(anchor="w", padx=7, pady=(0, 6))

        icon_box = tk.LabelFrame(self.fields_container, text="Icon / SVG", bg=PANEL, fg=CYAN, bd=1)
        icon_box.pack(fill="x", padx=10, pady=5)
        self.icon_name_var = tk.StringVar(value="None")
        tk.Label(icon_box, textvariable=self.icon_name_var, fg=TEXT, bg=PANEL).pack(side="left", padx=6, pady=6)
        tk.Button(icon_box, text="Library…", command=self.open_icon_library).pack(side="right", padx=6, pady=5)

        tk.Button(self.fields_container, text="Apply Selected Control", command=self.apply_properties, bg="#301519", fg="#fff").pack(fill="x", padx=10, pady=7)

        theme_box = tk.LabelFrame(self.fields_container, text="Theme", bg=PANEL, fg=CYAN)
        theme_box.pack(fill="x", padx=10, pady=(5, 12))
        for key, label in [("normal", "Normal"), ("shift", "G-Shift"), ("cyan", "Cyan"), ("panel_border", "Panel Border")]:
            tk.Button(theme_box, text=label, command=lambda k=key: self.choose_color(k)).pack(side="left", padx=3, pady=5)

    # ---------- inspector / image panel ----------
    def toggle_inspector(self):
        if self.inspector_visible: self._hide_inspector()
        else: self._show_inspector()

    def _hide_inspector(self, save=True):
        if self.inspector_visible:
            try:
                self.ui_state["inspector_width"] = max(220, self.inspector_frame.winfo_width())
                self.body_pane.forget(self.inspector_frame)
            except Exception:
                pass
        self.inspector_visible = False
        self.inspector_toggle_var.set("Show Inspector")
        if save: self._save_ui_state()

    def _show_inspector(self):
        if not self.inspector_visible:
            self.body_pane.add(self.inspector_frame, minsize=220)
        self.inspector_visible = True
        self.inspector_toggle_var.set("Hide Inspector")
        self.after(20, self._restore_pane_width)
        self._save_ui_state()

    def toggle_image_select(self):
        if self.image_select_open: self._hide_image_select()
        else: self._show_image_select()

    def _show_image_select(self):
        if not self.image_select_frame.winfo_manager():
            self.image_select_frame.pack(fill="x", before=self.body_pane)
        self.image_select_open = True
        self._refresh_image_select_panel()
        self._save_ui_state()

    def _hide_image_select(self):
        if self.image_select_frame.winfo_manager(): self.image_select_frame.pack_forget()
        self.image_select_open = False
        self._save_ui_state()

    def _asset_name(self, cfg: Dict[str, Any]) -> str:
        asset = cfg.get("asset") or {}
        return str(asset.get("name", "None")) if asset else "None"

    def _refresh_image_select_panel(self):
        if not hasattr(self, "image_vars"): return
        for kind in ("background", "controller"):
            cfg = self.project.setdefault(kind, {})
            self.image_vars[f"{kind}_asset"].set(self._asset_name(cfg))
            for key in ("x", "y", "width", "height"):
                self.image_vars[f"{kind}_{key}"].set(str(cfg.get(key, "")))

    def apply_image_geometry(self):
        try:
            for kind in ("background", "controller"):
                cfg = self.project.setdefault(kind, {})
                for key in ("x", "y", "width", "height"):
                    cfg[key] = int(self.image_vars[f"{kind}_{key}"].get())
                cfg["width"] = max(1, cfg["width"]); cfg["height"] = max(1, cfg["height"])
            self._set_dirty(); self.refresh_preview(); self.status_var.set("Image geometry updated")
        except Exception as e:
            messagebox.showerror("Invalid image geometry", str(e), parent=self)

    # ---------- project helpers ----------
    def _ensure_builtin_icons(self):
        icon_dir = Path(__file__).resolve().parents[1] / "assets" / "icons"
        existing = {a.get("id") for a in self.project.setdefault("asset_library", [])}
        for path in sorted(icon_dir.glob("*.svg")):
            aid = f"builtin:{path.stem}"
            if aid not in existing:
                add_asset(self.project, path, asset_id=aid, name=path.name)

    def current_card(self):
        for c in self.project.get("cards", []):
            if c.get("id") == self.selected_card_id: return c
        return None

    def selected_cards(self):
        ids = set(self.selected_card_ids)
        if self.selected_card_id: ids.add(self.selected_card_id)
        return [c for c in self.project.get("cards", []) if c.get("id") in ids]

    def _snap(self, value: float) -> int:
        if not getattr(self, "snap_enabled_var", None) or not self.snap_enabled_var.get():
            return int(round(value))
        try: size=max(1,int(self.snap_size_var.get()))
        except Exception: size=10
        return int(round(float(value)/size)*size)

    def _card_at(self, x: float, y: float) -> Optional[Dict[str, Any]]:
        for card in reversed(self.project.get("cards", [])):
            if card["x"] <= x <= card["x"] + card["width"] and card["y"] <= y <= card["y"] + card["height"]:
                return card
        return None

    def _controller_at(self, x: float, y: float) -> bool:
        c = self.project.get("controller", {})
        if not c.get("asset"): return False
        return int(c.get("x", 0)) <= x <= int(c.get("x", 0)) + int(c.get("width", 0)) and int(c.get("y", 0)) <= y <= int(c.get("y", 0)) + int(c.get("height", 0))

    def _select_card(self, card: Optional[Dict[str, Any]], bring_front: bool = True, additive: bool = False):
        self.selected_image_kind = None
        if card is None:
            if not additive:
                self.selected_card_id = None; self.selected_card_ids.clear()
            self.populate_properties(); self.refresh_preview(); return
        cid = card.get("id")
        if additive:
            if cid in self.selected_card_ids:
                self.selected_card_ids.remove(cid)
                if self.selected_card_id == cid:
                    self.selected_card_id = next(iter(self.selected_card_ids), None)
            else:
                self.selected_card_ids.add(cid); self.selected_card_id = cid
        else:
            self.selected_card_id = cid; self.selected_card_ids = {cid}
        if cid in self.selected_card_ids and bring_front:
            cards = self.project.get("cards", [])
            if cards and cards[-1] is not card:
                cards.remove(card); cards.append(card); sync_card_z_indices(self.project); self._set_dirty()
        self.populate_properties(); self.refresh_preview()

    def refresh_binding_choices(self):
        choices = [f"{r.get('section','')} :: {r.get('action','')}" for r in self.project.get("bindings", [])]
        self.binding_combo.configure(values=choices)
        if choices and self.binding_choice_var.get() not in choices: self.binding_choice_var.set(choices[0])

    def insert_binding_link(self, kind: str):
        choice = self.binding_choice_var.get()
        if " :: " not in choice: return
        if not self.active_content_text:
            messagebox.showinfo("Binding Link", "Click inside a Tap/Double/Hold field first, then insert the link.")
            return
        section, action = choice.split(" :: ", 1)
        self.active_content_text.insert("insert", make_binding_token(section, action, kind=kind))
        self.status_var.set(f"Inserted live {kind} link for {action}")

    # ---------- render/editor overlay ----------
    def refresh_preview(self):
        if self._render_after:
            try: self.after_cancel(self._render_after)
            except Exception: pass
        self._render_after = self.after(12, self._refresh_preview_now)

    def _refresh_preview_now(self):
        self._render_after = None
        try:
            im = render_project(self.project, self.selected_card_id)
            self._preview_photo = ImageTk.PhotoImage(im)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._preview_photo, tags=("preview",))
            self.canvas.configure(scrollregion=(0, 0, im.width, im.height))
            self._draw_editor_overlays()
        except Exception as e:
            self.status_var.set(f"Render error: {e}")

    def _draw_editor_overlays(self):
        # Multi-selected cards get a thin selection outline; the primary card
        # retains resize + connector handles.
        for sc in self.selected_cards():
            x, y, w, h = [int(sc[k]) for k in ("x", "y", "width", "height")]
            self.canvas.create_rectangle(x-2, y-2, x+w+2, y+h+2, outline=GREEN if sc.get("id") != self.selected_card_id else CYAN, width=2, dash=(5,3), tags=("editor_overlay", "multi_outline"))
        c = self.current_card()
        if c:
            ensure_card_content(c)
            x, y, w, h = [int(c[k]) for k in ("x", "y", "width", "height")]
            ax, ay = int(c["anchor_x"]), int(c["anchor_y"])
            mx, my = int(c.get("mid_x", ax)), int(c.get("mid_y", ay))
            hs = self.HANDLE_SIZE
            for name, hx, hy in [("nw", x, y), ("ne", x+w, y), ("sw", x, y+h), ("se", x+w, y+h)]:
                self.canvas.create_rectangle(hx-hs, hy-hs, hx+hs, hy+hs, fill=CYAN, outline="#fff", width=1, tags=("editor_overlay", f"resize:{name}"))
            self.canvas.create_oval(mx-10, my-10, mx+10, my+10, outline="#fff", width=2, fill=CYAN, tags=("editor_overlay", "mid_handle"))
            self.canvas.create_oval(ax-11, ay-11, ax+11, ay+11, outline=CYAN, width=3, fill="#071014", tags=("editor_overlay", "anchor_handle"))
            return
        if self.selected_image_kind == "controller":
            cfg=self.project.get("controller", {})
            if cfg.get("asset"):
                x,y,w,h=[int(cfg.get(k,0)) for k in ("x","y","width","height")]
                self.canvas.create_rectangle(x-2,y-2,x+w+2,y+h+2,outline=CYAN,width=2,dash=(7,3),tags=("editor_overlay","controller_outline"))
                hs=self.HANDLE_SIZE
                for name,hx,hy in [("nw",x,y),("ne",x+w,y),("sw",x,y+h),("se",x+w,y+h)]:
                    self.canvas.create_rectangle(hx-hs,hy-hs,hx+hs,hy+hs,fill=GREEN,outline="#fff",width=1,tags=("editor_overlay",f"controller-resize:{name}"))

    def _hit_handle(self, x: float, y: float) -> Optional[str]:
        c = self.current_card()
        if c:
            ax, ay = int(c["anchor_x"]), int(c["anchor_y"])
            mx, my = int(c.get("mid_x", ax)), int(c.get("mid_y", ay))
            if abs(x-ax) <= 14 and abs(y-ay) <= 14: return "anchor"
            if abs(x-mx) <= 14 and abs(y-my) <= 14: return "midpoint"
            cx, cy, w, h = [int(c[k]) for k in ("x", "y", "width", "height")]
            for name, hx, hy in [("nw", cx, cy), ("ne", cx+w, cy), ("sw", cx, cy+h), ("se", cx+w, cy+h)]:
                if abs(x-hx) <= 14 and abs(y-hy) <= 14: return f"resize-{name}"
        if self.selected_image_kind == "controller":
            cfg=self.project.get("controller", {})
            if cfg.get("asset"):
                cx,cy,w,h=[int(cfg.get(k,0)) for k in ("x","y","width","height")]
                for name,hx,hy in [("nw",cx,cy),("ne",cx+w,cy),("sw",cx,cy+h),("se",cx+w,cy+h)]:
                    if abs(x-hx) <= 14 and abs(y-hy) <= 14: return f"controller-resize-{name}"
        return None

    # ---------- persistent right-click menus ----------
    def _close_context_popup(self):
        if self._context_popup is not None:
            try: self._context_popup.destroy()
            except Exception: pass
        self._context_popup = None; self._context_kind = None; self._context_target = None

    def _show_context_popup(self, kind: str, event, card: Optional[Dict[str, Any]] = None):
        target = card.get("id") if card else kind
        self._close_context_popup()
        win = tk.Toplevel(self)
        self._context_popup = win; self._context_kind = kind; self._context_target = target
        win.overrideredirect(True)
        win.configure(bg="#d64742")
        win.geometry(f"+{event.x_root+4}+{event.y_root+4}")
        inner = tk.Frame(win, bg="#120b0d", bd=1, relief="solid")
        inner.pack(padx=1, pady=1)
        if kind == "card" and card:
            tk.Label(inner, text=f"{card.get('title','Card')}  •  Z {card.get('z_index',0)}", fg=RED, bg="#120b0d", font=("Sans", 10, "bold")).pack(fill="x", padx=8, pady=(6, 3))
            actions = [
                ("Edit in Inspector", self._context_edit_card),
                ("Text Size +", lambda: self.adjust_selected_text_size(+1)),
                ("Text Size −", lambda: self.adjust_selected_text_size(-1)),
                ("Icon / SVG Library…", self.open_icon_library),
                ("Duplicate Card", self.duplicate_card_cmd),
                ("Delete Card", self.delete_card_cmd),
            ]
        elif kind == "controller":
            tk.Label(inner, text="CONTROLLER / MOUSE IMAGE", fg=CYAN, bg="#120b0d", font=("Sans", 10, "bold")).pack(fill="x", padx=8, pady=(6, 3))
            actions = [("Replace Controller Image…", self.choose_controller_image), ("Clear Controller Image", self.clear_controller_image), ("Open Image Select", self._show_image_select)]
        else:
            tk.Label(inner, text="BACKGROUND", fg=CYAN, bg="#120b0d", font=("Sans", 10, "bold")).pack(fill="x", padx=8, pady=(6, 3))
            actions = [("Replace Background…", self.choose_background_image), ("Clear Background", self.clear_background_image), ("Open Image Select", self._show_image_select)]
        for label, cmd in actions:
            tk.Button(inner, text=label, command=cmd, anchor="w", bg="#211316", fg=TEXT, activebackground="#3c1d22", relief="flat", padx=8).pack(fill="x", padx=4, pady=1)
        tk.Label(inner, text="Right-click another target to move this menu. Double-right-click closes it.", fg=GREEN, bg="#120b0d", wraplength=260, justify="left").pack(fill="x", padx=8, pady=(5, 6))

    def _context_edit_card(self):
        self._show_inspector(); self.populate_properties()

    def canvas_right_click(self, event):
        x = self.canvas.canvasx(event.x); y = self.canvas.canvasy(event.y)
        card = self._card_at(x, y)
        if card:
            self._select_card(card, bring_front=True)
            self._show_context_popup("card", event, card)
        elif self._controller_at(x, y):
            self.selected_card_id=None; self.selected_card_ids.clear(); self.selected_image_kind="controller"; self.refresh_preview()
            self._show_context_popup("controller", event)
        else:
            self.selected_image_kind=None
            self._show_context_popup("background", event)
        return "break"

    def canvas_double_right_click(self, _event):
        self._close_context_popup(); return "break"

    # ---------- canvas interactions ----------
    def canvas_click(self, event):
        x = self.canvas.canvasx(event.x); y = self.canvas.canvasy(event.y)
        handle = self._hit_handle(x, y)
        if handle:
            self._interaction = handle; self._interaction_changed = False; self._drag_start = (x, y)
            c = self.current_card()
            self._drag_card_start = {k: int(c[k]) for k in ("x", "y", "width", "height", "mid_x", "mid_y", "anchor_x", "anchor_y")} if c else None
            if handle.startswith("controller-resize-"):
                cfg=self.project.get("controller", {}); self._drag_image_start={k:int(cfg.get(k,0)) for k in ("x","y","width","height")}
            return "break"
        clicked = self._card_at(x, y)
        additive = bool(getattr(event, "state", 0) & 0x0001)
        if clicked:
            self._select_card(clicked, bring_front=True, additive=additive)
            if clicked.get("id") not in self.selected_card_ids: return "break"
            self._interaction = "move"; self._interaction_changed = False; self._drag_start = (x, y)
            c=self.current_card(); self._drag_card_start = {k: int(c[k]) for k in ("x", "y", "width", "height", "mid_x", "mid_y", "anchor_x", "anchor_y")} if c else None
            self._drag_multi_start={sc["id"]:(int(sc["x"]),int(sc["y"])) for sc in self.selected_cards()}
        elif self._controller_at(x, y):
            self.selected_card_id=None; self.selected_card_ids.clear(); self.selected_image_kind="controller"
            cfg=self.project.get("controller", {}); self._drag_image_start={k:int(cfg.get(k,0)) for k in ("x","y","width","height")}
            self._interaction="controller-move"; self._interaction_changed=False; self._drag_start=(x,y); self._drag_card_start=None
            self.populate_properties(); self.refresh_preview()
        else:
            self._select_card(None, bring_front=False, additive=False)
            self.selected_image_kind=None; self._interaction = None; self._drag_start = None; self._drag_card_start = None; self._drag_multi_start={}

    def canvas_drag(self, event):
        if not self._drag_start: return
        x = self.canvas.canvasx(event.x); y = self.canvas.canvasy(event.y)
        dx = int(x - self._drag_start[0]); dy = int(y - self._drag_start[1])
        if self._interaction == "controller-move":
            s=self._drag_image_start or {}; cfg=self.project.get("controller", {})
            cfg["x"]=max(0,self._snap(s.get("x",0)+dx)); cfg["y"]=max(0,self._snap(s.get("y",0)+dy)); self._interaction_changed=True; self._refresh_image_select_panel(); self.refresh_preview(); return
        if self._interaction and self._interaction.startswith("controller-resize-"):
            s=self._drag_image_start or {}; cfg=self.project.get("controller", {}); corner=self._interaction.split("controller-resize-",1)[1]
            left,top=s.get("x",0),s.get("y",0); right=left+s.get("width",1); bottom=top+s.get("height",1)
            if "w" in corner: left=min(right-80,self._snap(s.get("x",0)+dx))
            if "e" in corner: right=max(left+80,self._snap(right+dx))
            if "n" in corner: top=min(bottom-60,self._snap(s.get("y",0)+dy))
            if "s" in corner: bottom=max(top+60,self._snap(bottom+dy))
            cfg.update({"x":max(0,left),"y":max(0,top),"width":right-left,"height":bottom-top}); self._interaction_changed=True; self._refresh_image_select_panel(); self.refresh_preview(); return
        if not self.selected_card_id or not self._drag_card_start: return
        card = self.current_card()
        if not card: return
        s = self._drag_card_start
        if self._interaction == "anchor":
            card["anchor_x"] = max(0, self._snap(x)); card["anchor_y"] = max(0, self._snap(y))
        elif self._interaction == "midpoint":
            card["mid_x"] = max(0, self._snap(x)); card["mid_y"] = max(0, self._snap(y))
        elif self._interaction == "move":
            for sc in self.selected_cards():
                ox,oy=self._drag_multi_start.get(sc["id"],(int(sc["x"]),int(sc["y"])))
                sc["x"] = max(0, self._snap(ox + dx)); sc["y"] = max(0, self._snap(oy + dy))
        elif self._interaction and self._interaction.startswith("resize-"):
            corner = self._interaction.split("-", 1)[1]
            left, top = s["x"], s["y"]; right, bottom = s["x"] + s["width"], s["y"] + s["height"]
            if "w" in corner: left = min(right - self.MIN_CARD_W, self._snap(s["x"] + dx))
            if "e" in corner: right = max(left + self.MIN_CARD_W, self._snap(right + dx))
            if "n" in corner: top = min(bottom - self.MIN_CARD_H, self._snap(s["y"] + dy))
            if "s" in corner: bottom = max(top + self.MIN_CARD_H, self._snap(bottom + dy))
            card["x"], card["y"], card["width"], card["height"] = max(0, left), max(0, top), right-left, bottom-top
        self._interaction_changed = True
        self.populate_properties(coords_only=True); self.refresh_preview()

    def canvas_release(self, _event):
        if self._interaction_changed: self._set_dirty()
        self._interaction = None; self._interaction_changed = False; self._drag_start = None; self._drag_card_start = None; self._drag_multi_start={}; self._drag_image_start=None

    def set_anchor(self, event):
        card = self.current_card()
        if not card: return "break"
        card["anchor_x"] = self._snap(self.canvas.canvasx(event.x)); card["anchor_y"] = self._snap(self.canvas.canvasy(event.y))
        self._set_dirty(); self.populate_properties(coords_only=True); self.refresh_preview(); return "break"

    def canvas_mousewheel(self, event):
        if not self.current_card(): return None
        if getattr(event, "num", None) == 4: delta = 1
        elif getattr(event, "num", None) == 5: delta = -1
        else: delta = 1 if getattr(event, "delta", 0) > 0 else -1
        self.adjust_selected_text_size(delta)
        return "break"

    def adjust_selected_text_size(self, delta: int):
        card = self.current_card()
        if not card: return
        ensure_card_content(card)
        old = int(card.get("text_size", 13))
        new = max(self.MIN_TEXT_SIZE, min(self.MAX_TEXT_SIZE, old + int(delta)))
        if new == old: return
        card["text_size"] = new
        grew_w, grew_h = ensure_card_fits_content(self.project, card)
        self._set_dirty(); self.populate_properties(coords_only=True); self.refresh_preview()
        growth = []
        if grew_w: growth.append("right side expanded")
        if grew_h: growth.append("bottom expanded")
        suffix = f" • {', '.join(growth)}" if growth else ""
        self.status_var.set(f"{card.get('title','Card')} text size: {new}{suffix}")

    # ---------- multi-selection / alignment ----------
    def align_selected(self, mode: str):
        cards=self.selected_cards()
        if len(cards) < 2:
            self.status_var.set("Shift-click two or more cards before using Align")
            return
        primary=self.current_card() or cards[-1]
        if mode == "left":
            target=int(primary["x"])
            for c in cards: c["x"]=target
        elif mode == "right":
            target=int(primary["x"])+int(primary["width"])
            for c in cards: c["x"]=target-int(c["width"])
        elif mode == "top":
            target=int(primary["y"])
            for c in cards: c["y"]=target
        elif mode == "bottom":
            target=int(primary["y"])+int(primary["height"])
            for c in cards: c["y"]=target-int(c["height"])
        elif mode == "hcenter":
            target=int(primary["x"])+int(primary["width"])//2
            for c in cards: c["x"]=target-int(c["width"])//2
        elif mode == "vcenter":
            target=int(primary["y"])+int(primary["height"])//2
            for c in cards: c["y"]=target-int(c["height"])//2
        elif mode == "distribute_h":
            ordered=sorted(cards,key=lambda c:int(c["x"]))
            if len(ordered)>2:
                first=int(ordered[0]["x"]); last=int(ordered[-1]["x"])
                step=(last-first)/(len(ordered)-1)
                for i,c in enumerate(ordered): c["x"]=self._snap(first+i*step)
        elif mode == "distribute_v":
            ordered=sorted(cards,key=lambda c:int(c["y"]))
            if len(ordered)>2:
                first=int(ordered[0]["y"]); last=int(ordered[-1]["y"])
                step=(last-first)/(len(ordered)-1)
                for i,c in enumerate(ordered): c["y"]=self._snap(first+i*step)
        else: return
        for c in cards:
            c["x"]=max(0,self._snap(c["x"])); c["y"]=max(0,self._snap(c["y"]))
        self._set_dirty(); self.populate_properties(coords_only=True); self.refresh_preview()
        self.status_var.set(f"Aligned {len(cards)} selected cards: {mode}")

    # ---------- inspector read/write ----------
    def populate_properties(self, coords_only=False):
        c = self.current_card()
        if not c:
            if not coords_only:
                for v in self.vars.values(): v.set("")
                for t in self.content_texts.values(): t.delete("1.0", "end")
                self.icon_name_var.set("None")
            return
        ensure_card_content(c)
        for key in self.vars: self.vars[key].set(str(c.get(key, "")))
        if not coords_only:
            for key, widget in self.content_texts.items():
                widget.delete("1.0", "end"); widget.insert("1.0", c["content"][key[0]].get(key[1], ""))
            asset = find_asset(self.project, c.get("icon_id")); self.icon_name_var.set(asset.get("name", "None") if asset else "None")

    def apply_properties(self):
        c = self.current_card()
        if not c: return
        try:
            c["title"] = self.vars["title"].get().strip() or "Mapping"
            for k in ("x", "y", "width", "height", "text_size", "mid_x", "mid_y", "anchor_x", "anchor_y"):
                c[k] = int(self.vars[k].get())
            c["width"] = max(self.MIN_CARD_W, c["width"]); c["height"] = max(self.MIN_CARD_H, c["height"])
            c["text_size"] = max(self.MIN_TEXT_SIZE, min(self.MAX_TEXT_SIZE, c["text_size"]))
            ensure_card_content(c)
            for (layer, gesture), widget in self.content_texts.items(): c["content"][layer][gesture] = widget.get("1.0", "end-1c")
            sync_card_legacy_text(c); ensure_card_fits_content(self.project, c)
            self._set_dirty(); self.status_var.set("Control properties updated; linked keys resolve live from Binding Table"); self.refresh_preview(); self.populate_properties(coords_only=True)
        except Exception as e:
            messagebox.showerror("Invalid properties", str(e))

    def choose_color(self, key):
        initial = self.project.get("theme", {}).get(key, DEFAULT_THEME.get(key, "#ffffff"))
        _, color = colorchooser.askcolor(initialcolor=initial, parent=self)
        if color:
            self.project.setdefault("theme", {})[key] = color; self._set_dirty(); self.refresh_preview()

    # ---------- image commands ----------
    def _choose_image_for(self, kind: str):
        title = "Choose background image" if kind == "background" else "Choose controller/mouse image"
        p = filedialog.askopenfilename(title=title, filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.svg"), ("All files", "*")])
        if not p: return
        try:
            self.project.setdefault(kind, {})["asset"] = encode_asset(p)
            if kind == "background":
                canvas = self.project.get("canvas", {})
                self.project[kind].setdefault("x", 0); self.project[kind].setdefault("y", 0)
                self.project[kind]["width"] = int(canvas.get("width", 1920)); self.project[kind]["height"] = int(canvas.get("height", 1080))
            self._set_dirty(); self._refresh_image_select_panel(); self.refresh_preview(); self.status_var.set(f"Updated {kind} image: {Path(p).name}")
        except Exception as e:
            messagebox.showerror("Asset import failed", str(e), parent=self)

    def choose_background_image(self): self._choose_image_for("background")
    def choose_controller_image(self): self._choose_image_for("controller")

    def clear_background_image(self):
        self.project.setdefault("background", {})["asset"] = None; self._set_dirty(); self._refresh_image_select_panel(); self.refresh_preview()

    def clear_controller_image(self):
        self.project.setdefault("controller", {})["asset"] = None; self._set_dirty(); self._refresh_image_select_panel(); self.refresh_preview()

    # ---------- project/file commands ----------
    def new_project_cmd(self):
        if not self._confirm_discard("starting a new project"): return
        self.project = new_project(); self.project_path = None; self.selected_card_id = None; self.selected_card_ids.clear(); self.selected_image_kind=None; self.dirty = False
        self._ensure_builtin_icons(); self.refresh_binding_choices(); self.refresh_preview(); self.populate_properties(); self._refresh_dependency_status(); self._refresh_image_select_panel(); self._update_title()

    def open_path(self, path: Path, as_template: bool = False):
        try:
            self.project = load_project(path); self._ensure_builtin_icons(); self.selected_card_id = None; self.selected_card_ids.clear(); self.selected_image_kind=None
            self.project_path = None if as_template else ensure_extension(path, ".udata")
            self.dirty = False
            if as_template:
                self.status_var.set("Loaded built-in template. First Save .udata will ask where you want the project stored.")
            else:
                self.status_var.set(f"Loaded {self.project_path}")
            self.refresh_binding_choices(); self.refresh_preview(); self.populate_properties(); self._refresh_dependency_status(); self._refresh_image_select_panel(); self._update_title()
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def open_project_cmd(self):
        if not self._confirm_discard("opening another project"): return
        p = filedialog.askopenfilename(title="Open .udata", filetypes=[("soloPAW udata", "*.udata"), ("JSON", "*.json"), ("All files", "*")])
        if p: self.open_path(Path(p), as_template=False)

    def save_project_cmd(self, force_as=False):
        path = self.project_path
        if force_as or path is None:
            p = filedialog.asksaveasfilename(
                title="Save .udata", initialdir=str(Path.home()),
                initialfile=(self.project.get("project", {}).get("name", "soloPAW Map") + ".udata"),
                defaultextension=".udata", filetypes=[("soloPAW udata", "*.udata")],
            )
            if not p: return False
            path = ensure_extension(p, ".udata")
        try:
            path = save_project(path, self.project)
            self.project_path = path; self._set_dirty(False); self.status_var.set(f"Saved .udata: {path}")
            return True
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return False

    def export_png_cmd(self):
        if not self.save_project_cmd(): return
        initial = (self.project_path.stem if self.project_path else "soloPAW Map") + ".png"
        p = filedialog.asksaveasfilename(title="Export PNG", initialdir=str(self.project_path.parent if self.project_path else Path.home()), initialfile=initial, defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not p: return
        try:
            out = export_png(p, self.project); self.status_var.set(f"Exported PNG: {out}")
        except Exception as e:
            messagebox.showerror("PNG export failed", str(e)); return
        if messagebox.askyesno("PNG exported", "Do you also need a G502 Remapper profile?"):
            self.export_remapper_cmd(default_dir=out.parent)
        if messagebox.askyesno("PNG exported", "Do you also need a Binding Table?"):
            self.export_binding_cmd(default_dir=out.parent)

    def export_bundle_cmd(self):
        if not self.save_project_cmd(): return
        initial=(self.project_path.stem if self.project_path else "soloPAW Map") + "_bundle.zip"
        p=filedialog.asksaveasfilename(title="Export Complete Bundle", initialdir=str(self.project_path.parent if self.project_path else Path.home()), initialfile=initial, defaultextension=".zip", filetypes=[("ZIP Bundle", "*.zip")])
        if not p: return
        try:
            out=export_bundle(p, self.project, project_source=self.project_path)
            self.status_var.set(f"Exported complete bundle: {out}")
            messagebox.showinfo("Bundle exported", "Created a portable bundle containing .udata, PNG, G502 Remapper, Binding Table JSON/CSV, manifest and SHA256 sums.", parent=self)
        except Exception as e: messagebox.showerror("Bundle export failed", str(e), parent=self)

    def export_remapper_cmd(self, default_dir: Optional[Path] = None):
        p = filedialog.asksaveasfilename(title="Export G502 Remapper", initialdir=str(default_dir or Path.home()), initialfile="G502 Remapper.json", defaultextension=".json", filetypes=[("Input Remapper JSON", "*.json")])
        if not p: return
        try:
            out = export_remapper(p, self.project); self.status_var.set(f"Exported G502 Remapper: {out}")
        except Exception as e: messagebox.showerror("Export failed", str(e))

    def export_binding_cmd(self, default_dir: Optional[Path] = None):
        p = filedialog.asksaveasfilename(title="Export Binding Table", initialdir=str(default_dir or Path.home()), initialfile="Binding Table.json", defaultextension=".json", filetypes=[("Binding Table base", "*.json")])
        if not p: return
        try:
            jp, cp = export_binding_table(p, self.project); self.status_var.set(f"Exported Binding Table: {jp.name}, {cp.name}")
        except Exception as e: messagebox.showerror("Export failed", str(e))

    # ---------- dependency / auxiliary windows ----------
    def _refresh_dependency_status(self):
        counts = dependency_counts(self.project); total = sum(counts.values())
        warn = sum(counts.get(k, 0) for k in ("stale", "conflict", "missing", "orphaned", "unresolved")); kept = counts.get("kept", 0)
        if warn: self.dependency_status_var.set(f"Deps: {total} • ⚠ {warn}")
        elif kept: self.dependency_status_var.set(f"Deps: {total} • manual {kept}")
        else: self.dependency_status_var.set(f"Deps: {total} ✓")

    def _dependency_changed(self):
        self._set_dirty(); self._refresh_dependency_status(); self.refresh_preview(); self.status_var.set("Remapper dependency model updated")

    def _binding_changed(self, change: Optional[Dict[str, Any]] = None):
        self._set_dirty(); self.refresh_binding_choices(); self.refresh_preview(); self._refresh_dependency_status()
        diags = dependency_diagnostics(self.project); warnings = [d for d in diags if d["status"] in ("stale", "conflict", "missing")]
        self.status_var.set(f"Binding Table updated — {count_binding_links(self.project)} visual links refreshed; {len(warnings)} remapper dependency warning(s)")
        if change and change.get("type") == "edit" and change.get("new", {}).get("id"):
            bid = change["new"]["id"]; affected = []
            for dep in self.project.get("remapper_profile", {}).get("dependencies", []):
                if bid in dep.get("binding_ids", []):
                    st = dependency_state(self.project, dep)
                    if st["status"] in ("stale", "conflict", "missing"): affected.append(dep["id"])
            old = change.get("old", {}); new = change.get("new", {})
            if affected and (old.get("primary") != new.get("primary") or old.get("secondary") != new.get("secondary")):
                BindingImpactDialog(self, change, affected)

    def open_bindings(self): BindingDialog(self, self.project, on_change=self._binding_changed)
    def open_remapper(self): RemapperDialog(self, self.project, on_change=self._dependency_changed)
    def open_dependencies(self): DependencyDialog(self, self.project, on_change=self._dependency_changed)
    def open_icon_library(self): IconLibraryDialog(self)

    # ---------- card commands ----------
    def add_card_cmd(self):
        offset = len(self.project.get("cards", [])) * 18
        c = add_card(self.project, x=70 + offset, y=120 + offset)
        self.selected_card_id = c["id"]; self.selected_card_ids={c["id"]}; self.selected_image_kind=None; self._set_dirty(); self.populate_properties(); self.refresh_preview()

    def duplicate_card_cmd(self):
        c = self.current_card()
        if not c: return
        dup = deepcopy(c); dup["id"] = str(uuid.uuid4()); dup["title"] = str(c.get("title", "Card")) + " Copy"
        for key in ("x", "y", "anchor_x", "anchor_y", "mid_x", "mid_y"): dup[key] = int(dup.get(key, 0)) + 24
        self.project.setdefault("cards", []).append(dup); sync_card_z_indices(self.project); self.selected_card_id = dup["id"]; self.selected_card_ids={dup["id"]}; self.selected_image_kind=None
        self._set_dirty(); self.populate_properties(); self.refresh_preview()

    def delete_card_cmd(self):
        if not self.selected_card_id: return
        self.project["cards"] = [c for c in self.project.get("cards", []) if c.get("id") != self.selected_card_id]
        sync_card_z_indices(self.project); self.selected_card_id = None; self.selected_card_ids.clear(); self._set_dirty(); self.populate_properties(); self.refresh_preview()


def run(default_project: Optional[Path] = None, initial_project: Optional[Path] = None):
    app = StudioApp(default_project=default_project, initial_project=initial_project)
    app.mainloop()
