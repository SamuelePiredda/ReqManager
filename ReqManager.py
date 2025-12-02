import sys
import json
import csv
import os
import ctypes
import html
import shutil
import re
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableView, 
                             QPushButton, QLabel, QDialog, QLineEdit, QComboBox, 
                             QTextEdit, QMessageBox, QFileDialog, QHeaderView, 
                             QSplitter, QRadioButton, QInputDialog, QFrame, QMenu, 
                             QStyle, QAbstractItemView, QGridLayout, QGroupBox)
from PyQt6.QtCore import QMarginsF, Qt, QSize, QTimer, QAbstractTableModel, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QColor, QFont, QIcon, QAction, QTextDocument
from PyQt6.QtPrintSupport import QPrinter

# --- CONSTANTS ---
CONFIG_FILE = "satreq_config.json"
ICON_NAME = "icon.ico"
VERSION = "5.6 Pro (Strict UX)"

# --- UTILS ---
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clean_html_fast(raw_html):
    if not raw_html: return ""
    cleanr_style = re.compile('<style.*?>.*?</style>', re.DOTALL)
    cleantext = re.sub(cleanr_style, '', raw_html)
    cleanr_tags = re.compile('<.*?>')
    cleantext = re.sub(cleanr_tags, '', cleantext)
    cleantext = html.unescape(cleantext)
    return cleantext.replace('\n', ' ').strip()

# --- MODEL ---
class RequirementsModel(QAbstractTableModel):
    def __init__(self, requirements=None):
        super().__init__()
        self._data = requirements or []
        self._headers = ["ID", "Type", "Description", "Target", "Unit", "Status", "Method", "Parent"]

    def update_data(self, requirements):
        self.beginResetModel()
        self._data = requirements
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        req = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return req['id']
            elif col == 1: return req.get('type', '-')
            elif col == 2: return clean_html_fast(req.get('desc', '')) 
            elif col == 3: return req.get('value', '')
            elif col == 4: return req.get('unit', '')
            elif col == 5: return req.get('status', '')
            elif col == 6: return req.get('method', '')
            elif col == 7: return req.get('parent_id', '')

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 5: 
                st = req.get('status', '')
                if "Verified" in st: return QColor("#006600") 
                if "TBD" in st or "TBC" in st: return QColor("#cc0000") 
                if "Closed" in st: return QColor("#666666") 

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def get_req_at(self, row_index):
        if 0 <= row_index < len(self._data):
            return self._data[row_index]
        return None

# --- DIALOGS ---
class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome - SatReq Pro")
        self.setMinimumWidth(450)
        if os.path.exists(ICON_NAME): self.setWindowIcon(QIcon(ICON_NAME))
        self.choice = None 
        layout = QVBoxLayout(self); layout.setSpacing(20)
        lbl = QLabel("Database not found.\nWhat would you like to do?")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        btn_open = QPushButton("  Open Existing"); btn_open.setMinimumHeight(45); btn_open.clicked.connect(self.select_open)
        btn_new = QPushButton("  Create New"); btn_new.setMinimumHeight(45); btn_new.clicked.connect(self.select_new)
        layout.addWidget(btn_open); layout.addWidget(btn_new)
    def select_open(self): self.choice = "OPEN"; self.accept()
    def select_new(self): self.choice = "NEW"; self.accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project"); self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project Name:"))
        self.inp_name = QLineEdit()
        layout.addWidget(self.inp_name)
        layout.addWidget(QLabel("Structure:"))
        self.radio_mission = QRadioButton("Standard (Mission, Payload, AOCS...)"); self.radio_mission.setChecked(True)
        self.radio_subsys = QRadioButton("Single Subsystem")
        layout.addWidget(self.radio_mission); layout.addWidget(self.radio_subsys)
        self.combo_sub = QComboBox(); self.combo_sub.addItems(["Mission", "Payload", "AOCS", "EPS", "TCS", "COMMS", "OBDH", "Structure", "Propulsion", "Ground Segment"]); self.combo_sub.setEnabled(False)
        layout.addWidget(QLabel("Subsystem (if single):")); layout.addWidget(self.combo_sub)
        self.radio_mission.toggled.connect(lambda: self.combo_sub.setEnabled(False))
        self.radio_subsys.toggled.connect(lambda: self.combo_sub.setEnabled(True))
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Create"); ok_btn.clicked.connect(self.validate_and_accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn); btn_box.addWidget(ok_btn)
        layout.addLayout(btn_box)
    def validate_and_accept(self):
        if not self.inp_name.text().strip(): QMessageBox.warning(self, "Error", "Project name empty."); return
        self.accept()
    def get_data(self): return (self.inp_name.text().strip(), self.radio_mission.isChecked(), self.combo_sub.currentText())

class RequirementDialog(QDialog):
    def __init__(self, parent, existing_ids, full_db, current_project, req_data=None):
        super().__init__(parent)
        self.setWindowTitle("Requirement Details"); self.setMinimumWidth(800); self.setMinimumHeight(500)
        self.existing_ids = existing_ids; self.full_db = full_db; self.current_project = current_project
        self.original_id = req_data.get('id', None) if req_data else None
        main_layout = QVBoxLayout(self); main_layout.setSpacing(20); main_layout.setContentsMargins(20, 20, 20, 20)
        
        gb_info = QGroupBox("Identification"); lay_info = QGridLayout(gb_info)
        self.inp_id = QLineEdit(); self.inp_id.setPlaceholderText("REQ-001")
        self.inp_type = QComboBox(); self.inp_type.addItems(["System", "Functional", "Performance", "Interface", "Environmental", "Design"])
        self.inp_parent = QLineEdit(); self.inp_parent.setPlaceholderText("Parent ID")
        lay_info.addWidget(QLabel("ID:"),0,0); lay_info.addWidget(self.inp_id,1,0)
        lay_info.addWidget(QLabel("Type:"),0,1); lay_info.addWidget(self.inp_type,1,1)
        lay_info.addWidget(QLabel("Parent:"),0,2); lay_info.addWidget(self.inp_parent,1,2)
        main_layout.addWidget(gb_info)

        gb_desc = QGroupBox("Description"); lay_desc = QVBoxLayout(gb_desc)
        self.inp_desc = QTextEdit(); self.inp_desc.setMinimumHeight(120); self.inp_desc.setAcceptRichText(True)
        lay_desc.addWidget(self.inp_desc)
        main_layout.addWidget(gb_desc, 1)

        gb_det = QGroupBox("Target & Verification"); lay_det = QGridLayout(gb_det)
        self.inp_value = QLineEdit(); self.inp_unit = QLineEdit()
        self.inp_status = QComboBox(); self.inp_status.addItems(["Draft", "TBC", "TBD", "Verified", "Closed"])
        self.inp_method = QComboBox(); self.inp_method.addItems(["Test", "Analysis", "Inspection", "Review of Design"])
        lay_det.addWidget(QLabel("Value:"),0,0); lay_det.addWidget(self.inp_value,1,0)
        lay_det.addWidget(QLabel("Unit:"),0,1); lay_det.addWidget(self.inp_unit,1,1)
        lay_det.addWidget(QLabel("Status:"),0,2); lay_det.addWidget(self.inp_status,1,2)
        lay_det.addWidget(QLabel("Method:"),0,3); lay_det.addWidget(self.inp_method,1,3)
        main_layout.addWidget(gb_det)

        btn_box = QHBoxLayout(); btn_box.addStretch()
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("SAVE"); self.btn_save.clicked.connect(self.validate_and_accept)
        btn_box.addWidget(btn_cancel); btn_box.addWidget(self.btn_save)
        main_layout.addLayout(btn_box)

        if req_data:
            self.inp_id.setText(req_data.get('id', '')); self.inp_type.setCurrentText(req_data.get('type', 'System'))
            if '<' in req_data.get('desc', ''): self.inp_desc.setHtml(req_data.get('desc', ''))
            else: self.inp_desc.setPlainText(req_data.get('desc', ''))
            self.inp_parent.setText(req_data.get('parent_id', '')); self.inp_value.setText(req_data.get('value', ''))
            self.inp_unit.setText(req_data.get('unit', '')); self.inp_status.setCurrentText(req_data.get('status', 'Draft'))
            self.inp_method.setCurrentText(req_data.get('method', 'Analysis'))

    def check_circular_dependency(self, target_id, new_parent_id):
        if not new_parent_id: return False
        if target_id == new_parent_id: return True 
        def find_req(rid):
            for sub in self.full_db[self.current_project].values():
                for r in sub:
                    if r['id'] == rid: return r
            return None
        current = find_req(new_parent_id)
        while current and current.get('parent_id'):
            pid = current['parent_id']
            if pid == target_id: return True 
            current = find_req(pid)
        return False

    def validate_and_accept(self):
        new_id = self.inp_id.text().strip()
        new_parent = self.inp_parent.text().strip()
        if not new_id: QMessageBox.warning(self, "Error", "ID mandatory."); return
        if " " in new_id: QMessageBox.warning(self, "Error", "ID no spaces."); return
        if new_id in self.existing_ids and new_id != self.original_id: QMessageBox.warning(self, "Error", "ID exists."); return
        if new_parent == new_id: QMessageBox.warning(self, "Error", "Self-parenting."); return
        if self.original_id and new_parent:
            if self.check_circular_dependency(self.original_id, new_parent):
                QMessageBox.critical(self, "Error", "Circular Dependency detected!"); return
        self.accept()
    
    def get_data(self):
        return {"id": self.inp_id.text().strip(), "type": self.inp_type.currentText(), "desc": self.inp_desc.toHtml(), "parent_id": self.inp_parent.text().strip(), "value": self.inp_value.text(), "unit": self.inp_unit.text(), "status": self.inp_status.currentText(), "method": self.inp_method.currentText(), "last_modified": get_timestamp(), "needs_review": False}

class ChildrenViewDialog(QDialog):
    def __init__(self, parent, parent_id, children_data):
        super().__init__(parent)
        self.setWindowTitle(f"Children of {parent_id}"); self.resize(800, 450)
        layout = QVBoxLayout(self)
        table = QTableView()
        model = RequirementsModel(children_data)
        table.setModel(model)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(False)
        layout.addWidget(table)
        layout.addWidget(QPushButton("Close", clicked=self.accept))

# --- MAIN APP ---
class SatReqManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SatReq Manager {VERSION}")
        if os.path.exists(ICON_NAME): self.setWindowIcon(QIcon(ICON_NAME))
        self.resize(1200, 750)
        self.data = {}; self.current_project = None; self.current_subsystem = None; self.db_path = None
        self.setup_ui()
        QTimer.singleShot(100, self.check_and_load_startup)

    def setup_ui(self):
        mb = self.menuBar(); fm = mb.addMenu('File')
        fm.addAction(QAction('Open...', self, triggered=self.open_existing_db_dialog))
        fm.addAction(QAction('New...', self, triggered=self.create_new_db_dialog))
        fm.addSeparator()
        self.act_save = QAction('Save', self, triggered=self.save_database); fm.addAction(self.act_save)
        self.act_csv = QAction('Export CSV', self, triggered=self.export_csv); fm.addAction(self.act_csv)
        self.act_pdf = QAction('Export PDF', self, triggered=self.export_pdf); fm.addAction(self.act_pdf)
        # Disabilito export all'avvio
        self.act_csv.setEnabled(False); self.act_pdf.setEnabled(False)

        mw = QWidget(); self.setCentralWidget(mw); main_layout = QHBoxLayout(mw)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget(); lv = QVBoxLayout(left)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self.on_tree_click)
        lv.addWidget(QLabel("Project Structure:")); lv.addWidget(self.tree)
        
        ltools = QGridLayout()
        self.btn_np = QPushButton("New Proj"); self.btn_np.clicked.connect(self.add_project)
        self.btn_ep = QPushButton("Rename Proj"); self.btn_ep.clicked.connect(self.rename_project); self.btn_ep.setEnabled(False)
        self.btn_dp = QPushButton("Del Proj"); self.btn_dp.clicked.connect(self.delete_project); self.btn_dp.setEnabled(False)
        
        self.btn_add_sub = QPushButton("+ Subsys"); self.btn_add_sub.clicked.connect(self.add_subsystem); self.btn_add_sub.setEnabled(False)
        self.btn_ren_sub = QPushButton("Rename Sub"); self.btn_ren_sub.clicked.connect(self.rename_subsystem); self.btn_ren_sub.setEnabled(False)
        self.btn_del_sub = QPushButton("- Subsys"); self.btn_del_sub.clicked.connect(self.delete_subsystem); self.btn_del_sub.setEnabled(False)
        
        ltools.addWidget(self.btn_np, 0, 0, 1, 2)
        ltools.addWidget(self.btn_ep, 1, 0); ltools.addWidget(self.btn_dp, 1, 1)
        ltools.addWidget(self.btn_add_sub, 2, 0); ltools.addWidget(self.btn_del_sub, 2, 1)
        ltools.addWidget(self.btn_ren_sub, 3, 0, 1, 2)
        lv.addLayout(ltools)

        right = QWidget(); rv = QVBoxLayout(right)
        rbar = QHBoxLayout()
        self.lbl_title = QLabel("Dashboard"); self.lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.search = QLineEdit(); self.search.setPlaceholderText("Search all columns..."); self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.apply_filter); self.search.setEnabled(False)
        
        self.btn_nr = QPushButton("+ Req"); self.btn_nr.setEnabled(False); self.btn_nr.clicked.connect(self.add_requirement)
        self.btn_dr = QPushButton("Delete"); self.btn_dr.setEnabled(False); self.btn_dr.clicked.connect(self.delete_requirement)
        
        rbar.addWidget(self.lbl_title); rbar.addStretch(); rbar.addWidget(self.search); rbar.addWidget(self.btn_nr); rbar.addWidget(self.btn_dr)
        rv.addLayout(rbar)

        self.table = QTableView()
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        
        self.model = RequirementsModel([])
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1) 
        
        self.table.setModel(self.proxy)
        self.table.doubleClicked.connect(self.edit_requirement)
        # Update UI state on row selection
        self.table.selectionModel().selectionChanged.connect(self.update_ui_state)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        rv.addWidget(self.table)
        splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([280, 920])
        main_layout.addWidget(splitter)

    # --- UI STATE MANAGEMENT ( STRICT UX ) ---
    def update_ui_state(self):
        # Determine what is selected
        has_proj = self.current_project is not None
        has_sub = self.current_subsystem is not None
        has_row_sel = self.table.selectionModel().hasSelection()
        
        # Project Level Actions
        self.btn_ep.setEnabled(has_proj) # Rename Proj
        self.btn_dp.setEnabled(has_proj) # Del Proj
        self.btn_add_sub.setEnabled(has_proj) # Add Sub
        self.act_csv.setEnabled(has_proj) # Export
        self.act_pdf.setEnabled(has_proj) # Export
        
        # Subsystem Level Actions
        self.btn_ren_sub.setEnabled(has_sub) # Rename Sub
        self.btn_del_sub.setEnabled(has_sub) # Del Sub
        self.btn_nr.setEnabled(has_sub) # Add Req
        self.search.setEnabled(has_sub) # Search
        
        # Table Row Actions
        self.btn_dr.setEnabled(has_row_sel) # Delete Req

    # --- LOGIC ---
    def load_table(self):
        if not self.current_project or not self.current_subsystem: return
        reqs = self.data[self.current_project][self.current_subsystem]
        self.model.update_data(reqs)
        self.table.resizeColumnToContents(0) 
        self.table.resizeColumnToContents(1) 
        self.table.setColumnWidth(2, 400) 

    def apply_filter(self, text):
        self.proxy.setFilterFixedString(text)

    # --- TREE ACTIONS ---
    def refresh_tree(self):
        self.tree.clear()
        for proj_name, subsystems in self.data.items():
            p_node = QTreeWidgetItem(self.tree); p_node.setText(0, f"📦 {proj_name}"); p_node.setData(0, Qt.ItemDataRole.UserRole, proj_name) 
            p_node.setFont(0, QFont("Segoe UI", 13, QFont.Weight.Bold))
            std_order = ["Mission","Payload","AOCS","EPS","TCS","COMMS","OBDH","Structure"]
            sorted_keys = sorted(subsystems.keys(), key=lambda x: std_order.index(x) if x in std_order else 99)
            for sub in sorted_keys:
                s_node = QTreeWidgetItem(p_node); s_node.setText(0, f"{sub} ({len(subsystems[sub])})")
                s_node.setData(0, Qt.ItemDataRole.UserRole, sub)
            p_node.setExpanded(True)

    def on_tree_click(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if item.parent(): 
            self.current_project = item.parent().data(0, Qt.ItemDataRole.UserRole)
            self.current_subsystem = data
            self.lbl_title.setText(f"{self.current_project}  /  {self.current_subsystem}")
            self.load_table()
        else: 
            self.current_project = data; self.current_subsystem = None
            self.lbl_title.setText(f"Project: {self.current_project}")
            self.model.update_data([])
        
        self.update_ui_state() # TRIGGER UI UPDATE

    def add_subsystem(self):
        if not self.current_project: return
        new_sub, ok = QInputDialog.getText(self, "New Subsystem", "Name:")
        if ok and new_sub:
            if new_sub in self.data[self.current_project]: QMessageBox.warning(self,"Error", "Subsystem already exists."); return
            self.data[self.current_project][new_sub] = []; self.refresh_tree(); self.save_database()
            # Restore selection context if possible (simplified here to just refresh)
            self.update_ui_state()
    
    def rename_subsystem(self):
        if not self.current_subsystem: return
        new_name, ok = QInputDialog.getText(self, "Rename Subsystem", "New Name:", text=self.current_subsystem)
        if ok and new_name and new_name != self.current_subsystem:
            if new_name in self.data[self.current_project]: QMessageBox.warning(self, "Error", "Name already exists."); return
            self.data[self.current_project][new_name] = self.data[self.current_project].pop(self.current_subsystem)
            self.current_subsystem = new_name; self.save_database(); self.refresh_tree(); self.lbl_title.setText(f"{self.current_project}  /  {self.current_subsystem}")

    def delete_subsystem(self):
        if not self.current_subsystem: return
        count = len(self.data[self.current_project][self.current_subsystem])
        if QMessageBox.question(self, "Delete", f"Delete '{self.current_subsystem}'?\nContains {count} requirements.", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.data[self.current_project][self.current_subsystem]
            self.current_subsystem = None 
            self.model.update_data([]) 
            self.lbl_title.setText(f"Project: {self.current_project}")
            self.save_database(); self.refresh_tree(); self.update_ui_state()

    def get_all_ids(self):
        ids = set()
        for s in self.data[self.current_project].values():
            for r in s: ids.add(r['id'])
        return ids

    def add_requirement(self):
        if not self.current_subsystem: return
        d = RequirementDialog(self, self.get_all_ids(), self.data, self.current_project)
        if d.exec(): 
            self.data[self.current_project][self.current_subsystem].append(d.get_data())
            self.search.clear(); self.save_database(); self.load_table(); self.refresh_tree()

    def edit_requirement(self, index):
        source_idx = self.proxy.mapToSource(index)
        req = self.model.get_req_at(source_idx.row())
        if not req: return
        d = RequirementDialog(self, self.get_all_ids(), self.data, self.current_project, req)
        if d.exec():
            new_data = d.get_data()
            if new_data['id'] != req['id']: self.update_parent_refs(req['id'], new_data['id'])
            req.update(new_data); self.save_database(); self.load_table()

    def delete_requirement(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes: return
        source_idx = self.proxy.mapToSource(indexes[0])
        req = self.model.get_req_at(source_idx.row())
        orphans = self.check_orphans(req['id'])
        msg = f"Delete '{req['id']}'?"
        if orphans: msg += f"\nWarning: Has {len(orphans)} children."
        if QMessageBox.question(self, "Delete", msg, QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if orphans: self.clean_orphans(req['id'])
            self.data[self.current_project][self.current_subsystem].remove(req)
            self.save_database(); self.load_table(); self.refresh_tree(); self.update_ui_state()

    def update_parent_refs(self, old, new):
        for s in self.data[self.current_project].values():
            for r in s: 
                if r.get('parent_id')==old: r['parent_id']=new; r['needs_review']=True
    def check_orphans(self, pid):
        return [r['id'] for s in self.data[self.current_project].values() for r in s if r.get('parent_id')==pid]
    def clean_orphans(self, pid):
        for s in self.data[self.current_project].values():
            for r in s: 
                if r.get('parent_id')==pid: r['parent_id']=""; r['needs_review']=True

    def add_project(self):
        d = NewProjectDialog(self)
        if d.exec():
            n, std, s = d.get_data()
            if n in self.data: QMessageBox.warning(self, "Error", "Project name already exists."); return
            self.data[n] = {k:[] for k in ["Mission","Payload","AOCS","EPS","TCS","COMMS","OBDH","Structure"]} if std else {s:[]}
            self.save_database(); self.refresh_tree(); self.update_ui_state()
    
    def rename_project(self):
        if not self.current_project: return
        n, ok = QInputDialog.getText(self, "Rename", "Name:", text=self.current_project)
        if ok and n and n!=self.current_project:
            if n in self.data: QMessageBox.warning(self, "Error", "Project name already exists."); return
            self.data[n] = self.data.pop(self.current_project)
            self.current_project = n # Update ref
            self.save_database(); self.refresh_tree(); self.lbl_title.setText(f"Project: {self.current_project}")

    def delete_project(self):
        if not self.current_project: return
        if QMessageBox.question(self,"Delete","Delete entire Project and all requirements?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            del self.data[self.current_project]
            self.current_project = None; self.current_subsystem = None
            self.save_database(); self.refresh_tree(); self.model.update_data([]); self.lbl_title.setText("Dashboard")
            self.update_ui_state()

    def check_and_load_startup(self):
        lp=None
        if os.path.exists(CONFIG_FILE):
            try: lp=json.load(open(CONFIG_FILE)).get("last_db_path")
            except: pass
        if lp and os.path.exists(lp): self.db_path=lp; self.load_database()
        else:
            d = StartupDialog(self)
            if d.exec(): 
                if d.choice=="OPEN": self.open_existing_db_dialog()
                elif d.choice=="NEW": self.create_new_db_dialog()
    def save_database(self):
        if self.db_path:
            try:
                tmp = self.db_path+".tmp"
                with open(tmp,'w') as f: json.dump(self.data, f, indent=4)
                shutil.move(tmp, self.db_path)
                with open(CONFIG_FILE,'w') as f: json.dump({"last_db_path":self.db_path}, f)
            except Exception as e: QMessageBox.critical(self,"Save Error",str(e))
    def load_database(self):
        try:
            shutil.copy2(self.db_path, self.db_path+".bak")
            self.data = json.load(open(self.db_path)); self.refresh_tree(); self.setWindowTitle(f"SatReq Manager {VERSION} - {os.path.basename(self.db_path)}")
            self.update_ui_state() # Init state
        except Exception as e: QMessageBox.critical(self,"Load Error",str(e))
    def open_existing_db_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,"Open","","JSON (*.json)"); 
        if p: self.db_path=p; self.load_database(); self.save_database()
    def create_new_db_dialog(self):
        p,_=QFileDialog.getSaveFileName(self,"New","","JSON (*.json)"); 
        if p: self.db_path=p; self.data={}; self.save_database(); self.load_database()
    
    def context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if not idx.isValid(): return
        source_idx = self.proxy.mapToSource(idx)
        req = self.model.get_req_at(source_idx.row())
        m = QMenu(); act = QAction(f"Trace Children: {req['id']}", self)
        act.triggered.connect(lambda: ChildrenViewDialog(self, req['id'], [r for s in self.data[self.current_project].values() for r in s if r.get('parent_id')==req['id']]).exec())
        m.addAction(act); m.exec(self.table.viewport().mapToGlobal(pos))
    
    def export_csv(self):
        if not self.current_project: return
        p,_ = QFileDialog.getSaveFileName(self, "Export CSV", f"{self.current_project}.csv", "CSV (*.csv)")
        if p:
            with open(p,'w',newline='',encoding='utf-8') as f:
                w=csv.writer(f); w.writerow(["ID","Type","Desc","Val","Unit","Status","Parent"])
                for s in self.data[self.current_project].values():
                    for r in s: w.writerow([r['id'],r.get('type',''),clean_html_fast(r.get('desc','')),r.get('value',''),r.get('unit',''),r.get('status',''),r.get('parent_id','')])
            QMessageBox.information(self,"OK","CSV Saved")
    def export_pdf(self):
        if not self.current_project: return
        p,_ = QFileDialog.getSaveFileName(self, "Export PDF", f"{self.current_project}.pdf", "PDF (*.pdf)")
        if p:
            html_c = f"<h1>{self.current_project}</h1>"
            for sub, reqs in self.data[self.current_project].items():
                if not reqs: continue
                html_c += f"<h2>{sub}</h2><table border='1' cellspacing='0' cellpadding='5' width='100%'><tr><th>ID</th><th>Type</th><th>Desc</th><th>Status</th></tr>"
                for r in reqs: html_c += f"<tr><td>{r['id']}</td><td>{r.get('type','')}</td><td>{clean_html_fast(r.get('desc',''))}</td><td>{r.get('status','')}</td></tr>"
                html_c += "</table>"
            printer = QPrinter(QPrinter.PrinterMode.HighResolution); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(p)
            doc = QTextDocument(); doc.setHtml(html_c); doc.print(printer); QMessageBox.information(self,"OK","PDF Saved")

if __name__ == '__main__':
    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet("QTableView{font-size:14px;}"); w = SatReqManager(); w.showMaximized(); sys.exit(app.exec())