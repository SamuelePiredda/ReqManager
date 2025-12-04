import sys
import json
import csv
import os
import html
import shutil
import re
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QDialog, QLineEdit, 
                             QComboBox, QTextEdit, QMessageBox, QFileDialog, QHeaderView, 
                             QSplitter, QRadioButton, QInputDialog, QFrame, QMenu, 
                             QStyle, QAbstractItemView, QGridLayout, QGroupBox)
from PyQt6.QtCore import QMarginsF, Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QAction, QTextDocument, QPageLayout
from PyQt6.QtPrintSupport import QPrinter

# --- CONSTANTS ---
CONFIG_FILE = "satreq_config.json"
ICON_NAME = "icon.ico"
VERSION = "7.6 Classic"

# --- UTILS ---
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clean_html_smart(raw_html):
    """Pulisce l'HTML per l'export mantenendo spazi corretti."""
    if not raw_html: return ""
    cleanr_style = re.compile('<style.*?>.*?</style>', re.DOTALL)
    text = re.sub(cleanr_style, '', raw_html)
    text = text.replace('</div>', ' ').replace('</p>', ' ').replace('<br>', ' ').replace('<br/>', ' ')
    cleanr_tags = re.compile('<.*?>')
    text = re.sub(cleanr_tags, '', text)
    text = html.unescape(text)
    return " ".join(text.split())

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
        
        self.req_data = req_data if req_data else {
            'id': '', 'type': 'System', 'desc': '', 'parent_id': '', 'value': '', 'unit': '', 
            'status': 'Draft', 'method': 'Analysis', 'last_modified': '', 'needs_review': False
        }

        main_layout = QVBoxLayout(self); main_layout.setSpacing(20); main_layout.setContentsMargins(20, 20, 20, 20)
        
        gb_info = QGroupBox("Identification"); lay_info = QGridLayout(gb_info)
        self.inp_id = QLineEdit()
        
        # --- LOGICA AUTO-ID (Integrata nella UI originale) ---
        if not self.original_id:
            self.inp_id.setText(self.generate_next_id())
        else:
            self.inp_id.setText(self.req_data['id'])
        # -----------------------------------------------------

        self.inp_type = QComboBox(); self.inp_type.addItems(["System", "Functional", "Performance", "Interface", "Environmental", "Design", "Safety"])
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
        
        self.inp_status = QComboBox()
        self.status_opts = ["Draft", "TBD (To Be Defined)", "TBC (To Be Confirmed)", "Verified", "Closed", "Obsolete"]
        self.inp_status.addItems(self.status_opts)
        
        self.inp_method = QComboBox(); self.inp_method.addItems(["Test", "Analysis", "Inspection", "Review of Design", "Similarity"])
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

        # Popolamento
        self.inp_type.setCurrentText(self.req_data['type'])
        if '<' in self.req_data['desc']: self.inp_desc.setHtml(self.req_data['desc'])
        else: self.inp_desc.setPlainText(self.req_data['desc'])
        
        self.inp_parent.setText(self.req_data['parent_id'])
        self.inp_value.setText(self.req_data['value'])
        self.inp_unit.setText(self.req_data['unit'])
        
        current_status = self.req_data['status']
        index = self.inp_status.findText(current_status, Qt.MatchFlag.MatchFixedString)
        if index >= 0: self.inp_status.setCurrentIndex(index)
        else: self.inp_status.setCurrentText(current_status)
        
        self.inp_method.setCurrentText(self.req_data['method'])

    def generate_next_id(self):
        max_num = 0
        pattern = re.compile(r'^REQ-(\d+)$', re.IGNORECASE)
        for existing_id in self.existing_ids:
            match = pattern.match(existing_id)
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num: max_num = num
                except ValueError: continue
        return f"REQ-{max_num + 1:03d}"

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
        
        if new_parent:
            if new_parent not in self.existing_ids:
                QMessageBox.warning(self, "Error", f"Parent ID '{new_parent}' does not exist.")
                return

        if self.original_id and new_parent:
            if self.check_circular_dependency(self.original_id, new_parent):
                QMessageBox.critical(self, "Error", "Circular Dependency detected!"); return
        self.accept()
    
    def get_data(self):
        is_new_req = self.original_id is None
        return {
            "id": self.inp_id.text().strip(), 
            "type": self.inp_type.currentText(), 
            "desc": self.inp_desc.toHtml(), 
            "parent_id": self.inp_parent.text().strip(), 
            "value": self.inp_value.text(), 
            "unit": self.inp_unit.text(), 
            "status": self.inp_status.currentText(), 
            "method": self.inp_method.currentText(), 
            "last_modified": get_timestamp(), 
            "needs_review": self.req_data.get('needs_review', False) if not is_new_req else False
        }

class ChildrenViewDialog(QDialog):
    def __init__(self, parent, parent_id, children_data):
        super().__init__(parent)
        self.setWindowTitle(f"Children of {parent_id}"); self.resize(800, 450)
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        headers = ["ID", "Type", "Description", "Target", "Unit", "Status", "Method", "Parent"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True) 

        self.populate_table(children_data)
        layout.addWidget(self.table)
        layout.addWidget(QPushButton("Close", clicked=self.accept))
    
    def populate_table(self, data):
        self.table.setRowCount(0)
        for r_idx, req in enumerate(data):
            self.table.insertRow(r_idx)
            def mk_item(txt):
                it = QTableWidgetItem(str(txt))
                it.setFlags(it.flags() ^ Qt.ItemFlag.ItemIsEditable) 
                return it

            self.table.setItem(r_idx, 0, mk_item(req['id']))
            self.table.setItem(r_idx, 1, mk_item(req.get('type', '-')))
            self.table.setItem(r_idx, 2, mk_item(clean_html_smart(req.get('desc', ''))))
            self.table.setItem(r_idx, 3, mk_item(req.get('value', '')))
            self.table.setItem(r_idx, 4, mk_item(req.get('unit', '')))
            
            st_item = mk_item(req.get('status', ''))
            st_val = req.get('status', '')
            if "Verified" in st_val: st_item.setForeground(QColor("#006600"))
            elif "TBD" in st_val or "TBC" in st_val: st_item.setForeground(QColor("#cc0000"))
            elif "Closed" in st_val or "Obsolete" in st_val: st_item.setForeground(QColor("#666666"))
            self.table.setItem(r_idx, 5, st_item)

            self.table.setItem(r_idx, 6, mk_item(req.get('method', '')))
            self.table.setItem(r_idx, 7, mk_item(req.get('parent_id', '')))
        self.table.resizeRowsToContents()

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
        self.act_csv.setEnabled(False); self.act_pdf.setEnabled(False)

        mw = QWidget(); self.setCentralWidget(mw); main_layout = QHBoxLayout(mw)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget(); lv = QVBoxLayout(left)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self.on_tree_click)
        lv.addWidget(QLabel("Project Structure:")); lv.addWidget(self.tree)
        
        # --- CLASSIC LEFT TOOLBAR LAYOUT (GRID) ---
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
        # ------------------------------------------

        right = QWidget(); rv = QVBoxLayout(right)
        rbar = QHBoxLayout()
        self.lbl_title = QLabel("Dashboard"); self.lbl_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.search = QLineEdit(); self.search.setPlaceholderText("Search all columns..."); self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.apply_filter); self.search.setEnabled(False)
        
        self.btn_nr = QPushButton("+ Req"); self.btn_nr.setEnabled(False); self.btn_nr.clicked.connect(self.add_requirement)
        
        self.btn_up = QPushButton("▲"); self.btn_up.setFixedWidth(30); self.btn_up.setToolTip("Move Up")
        self.btn_up.clicked.connect(self.move_requirement_up); self.btn_up.setEnabled(False)
        
        self.btn_down = QPushButton("▼"); self.btn_down.setFixedWidth(30); self.btn_down.setToolTip("Move Down")
        self.btn_down.clicked.connect(self.move_requirement_down); self.btn_down.setEnabled(False)

        self.btn_dr = QPushButton("Delete"); self.btn_dr.setEnabled(False); self.btn_dr.clicked.connect(self.delete_requirement)
        
        rbar.addWidget(self.lbl_title); rbar.addStretch()
        rbar.addWidget(self.search)
        rbar.addWidget(self.btn_up); rbar.addWidget(self.btn_down) 
        rbar.addWidget(self.btn_nr); rbar.addWidget(self.btn_dr)
        rv.addLayout(rbar)

        self.table = QTableWidget()
        self.table_headers = ["ID", "Type", "Description", "Target", "Unit", "Status", "Method", "Parent", "Review"]
        self.table.setColumnCount(len(self.table_headers))
        self.table.setHorizontalHeaderLabels(self.table_headers)
        
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) 
        self.table.setWordWrap(True)

        self.table.doubleClicked.connect(self.edit_requirement)
        self.table.itemSelectionChanged.connect(self.update_ui_state)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) 
        
        rv.addWidget(self.table)
        splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([280, 920])
        main_layout.addWidget(splitter)

    # --- UI STATE MANAGEMENT ---
    def update_ui_state(self):
        has_proj = self.current_project is not None
        has_sub = self.current_subsystem is not None
        has_row_sel = len(self.table.selectedItems()) > 0
        curr_row = self.table.currentRow()
        row_count = self.table.rowCount()
        is_searching = self.search.text() != ""
        
        self.btn_ep.setEnabled(has_proj)
        self.btn_dp.setEnabled(has_proj)
        self.btn_add_sub.setEnabled(has_proj)
        self.act_csv.setEnabled(has_proj)
        self.act_pdf.setEnabled(has_proj)
        
        self.btn_ren_sub.setEnabled(has_sub)
        self.btn_del_sub.setEnabled(has_sub)
        self.btn_nr.setEnabled(has_sub)
        self.search.setEnabled(has_sub)
        
        self.btn_dr.setEnabled(has_row_sel)
        
        can_move = has_row_sel and not is_searching
        self.btn_up.setEnabled(can_move and curr_row > 0)
        self.btn_down.setEnabled(can_move and curr_row < row_count - 1)

    # --- LOGIC ---
    def load_table(self):
        if not self.current_project or not self.current_subsystem: 
            self.table.setRowCount(0); return

        reqs = self.data[self.current_project].get(self.current_subsystem, [])
        self.table.setRowCount(0) 

        for r_idx, req in enumerate(reqs):
            self.table.insertRow(r_idx)

            def create_item(text, align=Qt.AlignmentFlag.AlignLeft):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | align)
                return item

            item_id = create_item(req['id'])
            item_id.setData(Qt.ItemDataRole.UserRole, req) 
            self.table.setItem(r_idx, 0, item_id)

            self.table.setItem(r_idx, 1, create_item(req.get('type', '-')))
            self.table.setItem(r_idx, 2, create_item(clean_html_smart(req.get('desc', ''))))
            self.table.setItem(r_idx, 3, create_item(req.get('value', '')))
            self.table.setItem(r_idx, 4, create_item(req.get('unit', '')))
            
            item_status = create_item(req.get('status', ''))
            st = req.get('status', '')
            if "Verified" in st: item_status.setForeground(QColor("#006600")) 
            if "TBD" in st or "TBC" in st: item_status.setForeground(QColor("#cc0000")) 
            if "Closed" in st or "Obsolete" in st: item_status.setForeground(QColor("#666666")) 
            self.table.setItem(r_idx, 5, item_status)

            self.table.setItem(r_idx, 6, create_item(req.get('method', '')))
            self.table.setItem(r_idx, 7, create_item(req.get('parent_id', '')))

            # Review column
            needs_review = req.get('needs_review', False)
            item_review = create_item("YES" if needs_review else "NO")
            if needs_review: 
                item_review.setBackground(QColor("#FFCCCC")) 
                item_review.setToolTip("Richiede Revisione: ID o Parent ID modificato.")
            self.table.setItem(r_idx, 8, item_review)
            
        self.table.resizeColumnToContents(0) 
        self.table.resizeColumnToContents(1) 
        self.table.resizeColumnToContents(8) 
        self.table.resizeRowsToContents()
        
        if self.search.text(): self.apply_filter(self.search.text())

    def apply_filter(self, text):
        text = text.lower()
        rows = self.table.rowCount()
        cols = self.table.columnCount()
        for r in range(rows):
            match = False
            for c in range(cols):
                item = self.table.item(r, c)
                if item and text in item.text().lower(): match = True; break
            self.table.setRowHidden(r, not match)
        self.update_ui_state()

    # --- TREE ACTIONS ---
    def refresh_tree(self):
        self.tree.clear()
        for proj_name, subsystems in self.data.items():
            p_node = QTreeWidgetItem(self.tree); p_node.setText(0, f"📦 {proj_name}"); p_node.setData(0, Qt.ItemDataRole.UserRole, proj_name) 
            p_node.setFont(0, QFont("Segoe UI", 13, QFont.Weight.Bold))
            std_order = ["Mission","Payload","AOCS","EPS","TCS","COMMS","OBDH","Structure"]
            sorted_keys = sorted(subsystems.keys(), key=lambda x: (std_order.index(x) if x in std_order else 99, x))
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
            self.table.setRowCount(0)
        self.update_ui_state()

    def add_subsystem(self):
        if not self.current_project: return
        new_sub, ok = QInputDialog.getText(self, "New Subsystem", "Name:")
        if ok and new_sub:
            new_sub = new_sub.strip()
            if new_sub in self.data[self.current_project]: QMessageBox.warning(self,"Error", "Subsystem already exists."); return
            self.data[self.current_project][new_sub] = []; self.refresh_tree(); self.save_database()
            self.update_ui_state()
    
    def rename_subsystem(self):
        if not self.current_subsystem: return
        new_name, ok = QInputDialog.getText(self, "Rename Subsystem", "New Name:", text=self.current_subsystem)
        if ok and new_name:
            new_name = new_name.strip()
            if new_name == self.current_subsystem: return
            if new_name in self.data[self.current_project]: QMessageBox.warning(self, "Error", "Name already exists."); return
            self.data[self.current_project][new_name] = self.data[self.current_project].pop(self.current_subsystem)
            self.current_subsystem = new_name
            self.save_database(); self.refresh_tree(); self.lbl_title.setText(f"{self.current_project}  /  {self.current_subsystem}")

    def delete_subsystem(self):
        if not self.current_subsystem: return
        reqs = self.data[self.current_project][self.current_subsystem]
        
        # Check Orphans Risk
        orphans_risk = []
        ids_to_delete = {r['id'] for r in reqs}
        for s_name, s_reqs in self.data[self.current_project].items():
            if s_name == self.current_subsystem: continue
            for r in s_reqs:
                if r.get('parent_id') in ids_to_delete: orphans_risk.append(r['id'])
        
        msg = f"Delete '{self.current_subsystem}'?\nContains {len(reqs)} requirements."
        if orphans_risk: msg += f"\n\n⚠️ WARNING: The following requirements will lose their parents:\n{', '.join(orphans_risk[:5])}..."

        if QMessageBox.question(self, "Delete", msg, QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if orphans_risk:
                for s_reqs in self.data[self.current_project].values():
                    for r in s_reqs:
                        if r.get('parent_id') in ids_to_delete:
                            r['parent_id'] = ""; r['needs_review'] = True

            del self.data[self.current_project][self.current_subsystem]
            self.current_subsystem = None 
            self.table.setRowCount(0); self.lbl_title.setText(f"Project: {self.current_project}")
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

    def edit_requirement(self, index=None):
        if self.table.currentRow() < 0: return
        item = self.table.item(self.table.currentRow(), 0)
        req_original = item.data(Qt.ItemDataRole.UserRole)
        if not req_original: return
        
        d = RequirementDialog(self, self.get_all_ids(), self.data, self.current_project, req_original)
        if d.exec():
            new_data = d.get_data()
            req_list = self.data[self.current_project][self.current_subsystem]
            target_index = -1
            for i, r in enumerate(req_list):
                if r['id'] == req_original['id']:
                    target_index = i
                    break
            
            if target_index != -1:
                if new_data['id'] != req_original['id']: 
                    self.update_parent_refs(req_original['id'], new_data['id'])
                
                new_data['needs_review'] = False 
                req_list[target_index] = new_data
                self.save_database(); self.load_table(); self.refresh_tree()
            else:
                 QMessageBox.critical(self, "Error", "Could not find requirement to update.")

    def delete_requirement(self):
        if self.table.currentRow() < 0: return
        item = self.table.item(self.table.currentRow(), 0)
        req = item.data(Qt.ItemDataRole.UserRole)
        
        orphans = self.check_orphans(req['id'])
        msg = f"Delete '{req['id']}'?"
        if orphans: msg += f"\nWarning: Has {len(orphans)} children."
        if QMessageBox.question(self, "Delete", msg, QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if orphans: self.clean_orphans(req['id'])
            req_list = self.data[self.current_project][self.current_subsystem]
            req_list[:] = [r for r in req_list if r['id'] != req['id']]
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

    def move_requirement_up(self):
        row = self.table.currentRow()
        if row <= 0: return
        req_list = self.data[self.current_project][self.current_subsystem]
        req_list[row], req_list[row-1] = req_list[row-1], req_list[row]
        self.save_database(); self.load_table(); self.table.selectRow(row-1)
    
    def move_requirement_down(self):
        row = self.table.currentRow()
        req_list = self.data[self.current_project][self.current_subsystem]
        if row >= len(req_list) - 1: return
        req_list[row], req_list[row+1] = req_list[row+1], req_list[row]
        self.save_database(); self.load_table(); self.table.selectRow(row+1)

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
        if ok and n:
            n = n.strip()
            if n == self.current_project: return
            if n in self.data: QMessageBox.warning(self, "Error", "Project name already exists."); return
            self.data[n] = self.data.pop(self.current_project)
            self.current_project = n 
            self.save_database(); self.refresh_tree(); self.lbl_title.setText(f"Project: {self.current_project}")

    def delete_project(self):
        if not self.current_project: return
        if QMessageBox.question(self,"Delete","Delete entire Project and all requirements?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            del self.data[self.current_project]
            self.current_project = None; self.current_subsystem = None
            self.save_database(); self.refresh_tree(); self.table.setRowCount(0); self.lbl_title.setText("Dashboard")
            self.update_ui_state()

    # --- FILE I/O (SAFE) ---
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
                with open(tmp,'w', encoding='utf-8') as f: json.dump(self.data, f, indent=4)
                shutil.move(tmp, self.db_path)
                with open(CONFIG_FILE,'w', encoding='utf-8') as f: json.dump({"last_db_path":self.db_path}, f)
            except Exception as e: QMessageBox.critical(self,"Save Error",f"Impossibile salvare il database: {str(e)}")
                
    def load_database(self):
        try:
            if os.path.exists(self.db_path): shutil.copy2(self.db_path, self.db_path+".bak")
            with open(self.db_path, 'r', encoding='utf-8') as f: self.data = json.load(f)
            self.refresh_tree(); self.setWindowTitle(f"SatReq Manager {VERSION} - {os.path.basename(self.db_path)}"); self.update_ui_state() 
        except Exception as e: QMessageBox.critical(self,"Load Error",f"Impossibile caricare il database: {str(e)}")

    def open_existing_db_dialog(self):
        p,_=QFileDialog.getOpenFileName(self,"Open","","JSON (*.json)"); 
        if p: self.db_path=p; self.load_database(); self.save_database()
        
    def create_new_db_dialog(self):
        p,_=QFileDialog.getSaveFileName(self,"New","","JSON (*.json)"); 
        if p: self.db_path=p; self.data={}; self.save_database(); self.load_database()
    
    def context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        row = item.row()
        req_item = self.table.item(row, 0)
        req = req_item.data(Qt.ItemDataRole.UserRole)
        m = QMenu(); 
        act = QAction(f"Trace Children: {req['id']}", self)
        act.triggered.connect(lambda: ChildrenViewDialog(self, req['id'], [r for s in self.data[self.current_project].values() for r in s if r.get('parent_id')==req['id']]).exec())
        m.addAction(act); m.exec(self.table.viewport().mapToGlobal(pos))
    
    def export_csv(self):
        if not self.current_project: return
        p,_ = QFileDialog.getSaveFileName(self, "Export CSV", f"{self.current_project}.csv", "CSV (*.csv)")
        if p:
            # utf-8-sig per compatibilità Excel
            with open(p,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); 
                w.writerow(["ID","Type","Desc","Val","Unit","Status","Parent", "Needs Review"])
                for s in self.data[self.current_project].values():
                    for r in s: w.writerow([r['id'],r.get('type',''),clean_html_smart(r.get('desc','')),r.get('value',''),r.get('unit',''),r.get('status',''),r.get('parent_id',''), "YES" if r.get('needs_review', False) else "NO"])
            QMessageBox.information(self,"OK","CSV Saved")
            
    def export_pdf(self):
        if not self.current_project: return
        p, _ = QFileDialog.getSaveFileName(self, "Export PDF", f"{self.current_project}_Executive.pdf", "PDF (*.pdf)")
        if p:
            try:
                # CSS per stile Executive (Formale e Pulito)
                css = """
                <style>
                    body { font-family: Helvetica, Arial, sans-serif; }
                    h1 { color: #2c3e50; font-size: 24pt; margin-bottom: 5px; }
                    p.meta { color: #7f8c8d; font-size: 10pt; margin-bottom: 20px; }
                    h2 { color: #34495e; border-bottom: 2px solid #34495e; margin-top: 25px; font-size: 16pt; }
                    
                    table { border-collapse: collapse; width: 100%; font-size: 11pt; }
                    th { background-color: #ecf0f1; border: 1px solid #bdc3c7; padding: 8px; font-weight: bold; text-align: left; color: #2c3e50; }
                    td { border: 1px solid #bdc3c7; padding: 8px; vertical-align: top; }
                    
                    .status-draft { color: #95a5a6; font-style: italic; }
                    .status-ver { color: #27ae60; font-weight: bold; }
                    .status-tbd { color: #c0392b; font-weight: bold; }
                    .status-closed { color: #34495e; text-decoration: line-through; }
                </style>
                """
                
                html_c = f"{css}<h1>Project: {self.current_project}</h1><p class='meta'>Report • Generated: {get_timestamp()}</p>"
                
                # Itera sui sottosistemi ordinati
                for sub in sorted(self.data[self.current_project].keys()):
                    reqs = self.data[self.current_project][sub]
                    if not reqs: continue
                    
                    html_c += f"<h2>{sub}</h2>"
                    html_c += """
                    <table>
                        <tr>
                            <th>ID</th>
                            <th>Type</th>
                            <th>Description</th>
                            <th>Target</th>
                            <th>Unit</th>
                            <th>Status</th>
                            <th>Method</th>
                            <th>Parent</th>
                        </tr>
                    """
                    
                    for r in reqs:
                        desc = clean_html_smart(r.get('desc',''))
                        st = r.get('status','')
                        
                        st_class = ""
                        if "Verified" in st: st_class = "status-ver"
                        elif "TBD" in st or "TBC" in st: st_class = "status-tbd"
                        elif "Draft" in st: st_class = "status-draft"
                        elif "Closed" in st or "Obsolete" in st: st_class = "status-closed"
                        
                        html_c += f"""
                        <tr>
                            <td><b>{r['id']}</b></td>
                            <td>{r.get('type','')}</td>
                            <td>{desc}</td>
                            <td>{r.get('value','')}</td>
                            <td>{r.get('unit','')}</td>
                            <td class='{st_class}'>{st}</td>
                            <td>{r.get('method','')}</td>
                            <td>{r.get('parent_id','')}</td>                            
                        </tr>
                        """
                    html_c += "</table>"

                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(p)
                
                # --- CORREZIONE QUI ---
                printer.setPageOrientation(QPageLayout.Orientation.Landscape)
                # ----------------------
                
                doc = QTextDocument()
                doc.setHtml(html_c)
                doc.print(printer)
                QMessageBox.information(self,"Success","PDF exported successfully.")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))


if __name__ == '__main__':
    # Fix High DPI Windows
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("QTableWidget{font-size:14px;}") 
    w = SatReqManager()
    w.showMaximized()
    sys.exit(app.exec())