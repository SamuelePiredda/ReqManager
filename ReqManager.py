import sys
import json
import csv
import os
import ctypes
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTreeWidget, QTreeWidgetItem, QTableWidget, 
                             QTableWidgetItem, QPushButton, QLabel, QDialog, 
                             QFormLayout, QLineEdit, QComboBox, QTextEdit, 
                             QMessageBox, QFileDialog, QHeaderView, QSplitter,
                             QRadioButton, QInputDialog, QFrame, QMenu, QStyle, QAbstractItemView, QGridLayout)
from PyQt6.QtCore import QMarginsF, Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QAction, QPageLayout, QTextDocument
from PyQt6.QtPrintSupport import QPrinter

# --- CONSTANTS ---
CONFIG_FILE = "satreq_config.json"
ICON_NAME = "icon.ico"
VERSION = "3.4 Pro (With Filters)"  # Aggiornata versione

# --- STYLE (Dark Theme) ---
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', sans-serif; font-size: 12px;
}
QTreeWidget, QTableWidget {
    background-color: #252535; border: 1px solid #313244; border-radius: 4px; color: #ffffff; gridline-color: #45475a;
}
QHeaderView::section {
    background-color: #181825; padding: 4px; border: 1px solid #313244; color: #bac2de; font-weight: bold;
}
QPushButton {
    background-color: #313244; border: 1px solid #45475a; border-radius: 4px; color: #cdd6f4; padding: 6px 12px; font-weight: bold;
}
QPushButton:hover { background-color: #45475a; border-color: #89b4fa; }
QPushButton#BtnPrimary { background-color: #89b4fa; color: #1e1e2e; }
QPushButton#BtnDanger { color: #f38ba8; border-color: #f38ba8; }
QLineEdit, QTextEdit, QComboBox {
    background-color: #181825; border: 1px solid #313244; border-radius: 3px; color: #ffffff; padding: 4px;
}
QToolTip { background-color: #f9e2af; color: #1e1e2e; border: 1px solid #cdd6f4; }
QSplitter::handle { background-color: #45475a; height: 1px; }
"""

# --- UTILS ---
def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- DIALOGS ---

class StartupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome - SatReq Pro")
        self.setMinimumWidth(400)
        self.setStyleSheet(STYLESHEET)
        if os.path.exists(ICON_NAME): self.setWindowIcon(QIcon(ICON_NAME))
        self.choice = None 
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        lbl = QLabel("Database not found.\nWhat would you like to do?")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl)
        
        btn_open = QPushButton("  Open Existing")
        btn_open.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        btn_open.setMinimumHeight(40); btn_open.clicked.connect(self.select_open)
        
        btn_new = QPushButton("  Create New")
        btn_new.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        btn_new.setObjectName("BtnPrimary")
        btn_new.setMinimumHeight(40); btn_new.clicked.connect(self.select_new)
        
        layout.addWidget(btn_open); layout.addWidget(btn_new)
        
    def select_open(self): self.choice = "OPEN"; self.accept()
    def select_new(self): self.choice = "NEW"; self.accept()

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(350)
        self.setStyleSheet(STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project Name:"))
        self.inp_name = QLineEdit(); self.inp_name.setPlaceholderText("e.g. Sentinel-6")
        layout.addWidget(self.inp_name)
        
        layout.addWidget(QLabel("Structure:"))
        self.radio_mission = QRadioButton("Standard (Mission, Payload, AOCS...)")
        self.radio_subsys = QRadioButton("Single Subsystem")
        self.radio_mission.setChecked(True)
        layout.addWidget(self.radio_mission); layout.addWidget(self.radio_subsys)
        
        self.combo_sub = QComboBox()
        self.combo_sub.addItems(["Mission", "Payload", "AOCS", "EPS", "TCS", "COMMS", "OBDH", "Structure", "Propulsion", "Ground Segment"])
        self.combo_sub.setEnabled(False)
        layout.addWidget(QLabel("Subsystem (if single):")); layout.addWidget(self.combo_sub)
        
        self.radio_mission.toggled.connect(lambda: self.combo_sub.setEnabled(False))
        self.radio_subsys.toggled.connect(lambda: self.combo_sub.setEnabled(True))
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Create"); ok_btn.setObjectName("BtnPrimary"); ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn); btn_box.addWidget(ok_btn)
        layout.addLayout(btn_box)

    def get_data(self): return (self.inp_name.text().strip(), self.radio_mission.isChecked(), self.combo_sub.currentText())

class RequirementDialog(QDialog):
    def __init__(self, parent, existing_ids, req_data=None):
        super().__init__(parent)
        self.setWindowTitle("Requirement Details")
        self.setMinimumWidth(600)
        self.setStyleSheet(STYLESHEET)
        self.existing_ids = existing_ids
        self.original_id = req_data.get('id', None) if req_data else None

        self.layout = QFormLayout(self)
        
        self.inp_id = QLineEdit()
        self.inp_type = QComboBox(); self.inp_type.addItems(["System", "Functional", "Performance", "Interface", "Environmental", "Design"])
        
        # Use HTML for rich text
        self.inp_desc = QTextEdit(); self.inp_desc.setMaximumHeight(80)
        self.inp_desc.setAcceptRichText(True)
        
        self.inp_parent = QLineEdit(); self.inp_parent.setPlaceholderText("e.g. SYS-001 (Empty if root)")
        
        self.inp_value = QLineEdit()
        self.inp_unit = QLineEdit(); self.inp_unit.setFixedWidth(80)
        self.inp_status = QComboBox(); self.inp_status.addItems(["Draft", "TBC", "TBD", "Verified", "Closed"])
        self.inp_method = QComboBox(); self.inp_method.addItems(["Test", "Analysis", "Inspection", "Review of Design"])

        if req_data:
            self.inp_id.setText(req_data.get('id', ''))
            self.inp_type.setCurrentText(req_data.get('type', 'System'))
            # Legacy support for plain text and HTML
            if '<' in req_data.get('desc', ''): self.inp_desc.setHtml(req_data.get('desc', ''))
            else: self.inp_desc.setPlainText(req_data.get('desc', ''))
            self.inp_parent.setText(req_data.get('parent_id', '')) 
            self.inp_value.setText(req_data.get('value', ''))
            self.inp_unit.setText(req_data.get('unit', ''))
            self.inp_status.setCurrentText(req_data.get('status', 'Draft'))
            self.inp_method.setCurrentText(req_data.get('method', 'Analysis'))
        
        self.layout.addRow("Unique ID:", self.inp_id)
        self.layout.addRow("Type:", self.inp_type)
        self.layout.addRow("Description:", self.inp_desc)
        self.layout.addRow("Parent ID:", self.inp_parent)
        
        row_tgt = QHBoxLayout()
        row_tgt.addWidget(self.inp_value); row_tgt.addWidget(QLabel("Unit:")); row_tgt.addWidget(self.inp_unit)
        self.layout.addRow("Target:", row_tgt)
        
        self.layout.addRow("Status:", self.inp_status)
        self.layout.addRow("Verif. Method:", self.inp_method)
        
        self.btn_save = QPushButton("SAVE"); self.btn_save.setObjectName("BtnPrimary"); self.btn_save.clicked.connect(self.validate_and_accept)
        self.layout.addRow(self.btn_save)

    def validate_and_accept(self):
        new_id = self.inp_id.text().strip()
        if not new_id:
            QMessageBox.warning(self, "Error", "ID is mandatory.")
            return
        if new_id in self.existing_ids and new_id != self.original_id:
            QMessageBox.warning(self, "ID Error", f"The ID '{new_id}' already exists in this project!")
            return
        self.accept()

    def get_data(self):
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
            "needs_review": False 
        }

class ChildrenViewDialog(QDialog):
    def __init__(self, parent, parent_id, children_data):
        super().__init__(parent)
        self.setWindowTitle(f"Traceability: Derived from {parent_id}")
        self.resize(750, 400)
        self.setStyleSheet(STYLESHEET)
        
        layout = QVBoxLayout(self)
        lbl = QLabel(f"Children requirements of <b>{parent_id}</b> ({len(children_data)} found):")
        lbl.setStyleSheet("font-size: 14px; color: #89b4fa;")
        layout.addWidget(lbl)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Subsystem", "ID", "Description", "Status", "Last Modified"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Stretch Desc
        table.setRowCount(len(children_data))
        table.setWordWrap(True)
        
        for i, child in enumerate(children_data):
            table.setItem(i, 0, QTableWidgetItem(child.get('subsystem', '-')))
            table.setItem(i, 1, QTableWidgetItem(child['id']))
            # Clean HTML for quick table view
            plain_desc = QTextDocument(); plain_desc.setHtml(child['desc'])
            table.setItem(i, 2, QTableWidgetItem(plain_desc.toPlainText()))
            table.setItem(i, 3, QTableWidgetItem(child['status']))
            table.setItem(i, 4, QTableWidgetItem(child.get('last_modified', '-')))
        
        table.resizeRowsToContents() 
        layout.addWidget(table)
        layout.addWidget(QPushButton("Close", clicked=self.accept))

# --- MAIN APP ---
class SatReqManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SatReq Manager {VERSION}")
        if os.path.exists(ICON_NAME): 
            self.setWindowIcon(QIcon(ICON_NAME))
            try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('satreq.manager.pro')
            except: pass
        
        self.data = {} 
        self.current_project = None
        self.current_subsystem = None
        self.db_path = None
        
        self.init_ui()
        self.check_and_load_startup()

    def init_ui(self):
        # Menu
        mb = self.menuBar()
        fm = mb.addMenu('File')
        fm.addAction(QAction('Open Database...', self, triggered=self.open_existing_db_dialog))
        fm.addAction(QAction('Create New Database...', self, triggered=self.create_new_db_dialog))
        fm.addSeparator()
        fm.addAction(QAction('Save', self, triggered=self.save_database))
        fm.addAction(QAction('Export CSV', self, triggered=self.export_csv))
        fm.addAction(QAction('Export PDF', self, triggered=self.export_pdf))

        # Main Layout
        mw = QWidget(); self.setCentralWidget(mw)
        main_layout = QHBoxLayout(mw); main_layout.setContentsMargins(5,5,5,5)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL (TREE)
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0,0,0,0)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.itemClicked.connect(self.on_tree_click)
        
        # --- PROJECT BUTTONS (GRID LAYOUT for space efficiency) ---
        ptools = QGridLayout(); ptools.setSpacing(4)
        
        self.btn_np = QPushButton("New"); self.btn_np.setObjectName("BtnPrimary"); self.btn_np.clicked.connect(self.add_project)
        self.btn_ep = QPushButton("Edit"); self.btn_ep.clicked.connect(self.rename_project); self.btn_ep.setEnabled(False)
        self.btn_dp = QPushButton("DELETE PROJECT"); self.btn_dp.setObjectName("BtnDanger"); self.btn_dp.clicked.connect(self.delete_project); self.btn_dp.setEnabled(False)
        
        self.btn_add_sub = QPushButton("+ Subsystem"); self.btn_add_sub.clicked.connect(self.add_subsystem); self.btn_add_sub.setEnabled(False)
        self.btn_del_sub = QPushButton("- Subsystem"); self.btn_del_sub.clicked.connect(self.delete_subsystem); self.btn_del_sub.setEnabled(False)
        
        # Row 0: New | Edit
        ptools.addWidget(self.btn_np, 0, 0)
        ptools.addWidget(self.btn_ep, 0, 1)
        
        # Row 1: +Sub | -Sub
        ptools.addWidget(self.btn_add_sub, 1, 0)
        ptools.addWidget(self.btn_del_sub, 1, 1)
        
        # Row 2: Delete Project (Span 2 columns)
        ptools.addWidget(self.btn_dp, 2, 0, 1, 2)

        lv.addWidget(QLabel("PROJECT STRUCTURE", styleSheet="font-weight:bold; color:#89b4fa")); lv.addWidget(self.tree); lv.addLayout(ptools)

        # RIGHT PANEL (TABLE)
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(5,0,0,0)
        
        # Header
        self.lbl_title = QLabel("No Selection"); self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        hf = QFrame(); hf.setStyleSheet("background-color:#252535;border-radius:4px;padding:6px")
        hl = QHBoxLayout(hf); hl.addWidget(self.lbl_title); hl.addStretch()

        # Req Toolbar
        rtools = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("🔍 Search (ID, Desc...)"); self.search.setFixedWidth(200)
        self.search.textChanged.connect(self.apply_filter); self.search.setEnabled(False)
        
        # --- FILTER BY TYPE ---
        self.filter_type = QComboBox()
        self.filter_type.addItems(["All Types", "System", "Functional", "Performance", "Interface", "Environmental", "Design"])
        self.filter_type.setFixedWidth(120)
        self.filter_type.setEnabled(False)
        self.filter_type.currentTextChanged.connect(self.apply_filter)
        # -----------------------

        self.btn_nr = QPushButton(" + Req"); self.btn_nr.setObjectName("BtnPrimary"); self.btn_nr.setEnabled(False); self.btn_nr.clicked.connect(self.add_requirement)
        self.btn_dr = QPushButton(" Delete"); self.btn_dr.setObjectName("BtnDanger"); self.btn_dr.setEnabled(False); self.btn_dr.clicked.connect(self.delete_requirement)
        
        rtools.addWidget(self.search)
        rtools.addWidget(self.filter_type) # Added to Layout
        rtools.addStretch()
        rtools.addWidget(self.btn_nr); rtools.addWidget(self.btn_dr)

        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Type", "Description", "Target", "Unit", "Status", "Method", "Parent"])
        
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Description Stretches
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID Fits Content
        
        header.sectionResized.connect(self.table.resizeRowsToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True) 
        self.table.doubleClicked.connect(self.edit_requirement)
        self.table.itemSelectionChanged.connect(lambda: self.btn_dr.setEnabled(True))
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)

        rv.addWidget(hf); rv.addSpacing(5); rv.addLayout(rtools); rv.addWidget(self.table)

        splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([280, 1000])
        main_layout.addWidget(splitter)

    # --- CORE LOGIC ---
    def get_all_ids_in_project(self, project_name):
        ids = set()
        if project_name in self.data:
            for subsys in self.data[project_name].values():
                for req in subsys:
                    ids.add(req['id'])
        return ids

    def update_parent_references(self, old_id, new_id):
        count = 0
        for subsys_name, reqs in self.data[self.current_project].items():
            for r in reqs:
                if r.get('parent_id') == old_id:
                    r['parent_id'] = new_id
                    r['needs_review'] = True
                    count += 1
        if count > 0:
            QMessageBox.information(self, "Traceability Update", f"Updated {count} child requirements pointing to '{old_id}'.")

    def check_orphans(self, deleted_id):
        orphans = []
        for subsys_name, reqs in self.data[self.current_project].items():
            for r in reqs:
                if r.get('parent_id') == deleted_id:
                    orphans.append(r['id'])
        return orphans

    # --- UI LOADERS ---
    def refresh_tree(self):
        self.tree.clear()
        self.btn_ep.setEnabled(False); self.btn_dp.setEnabled(False)
        self.btn_add_sub.setEnabled(False); self.btn_del_sub.setEnabled(False)
        
        for proj_name, subsystems in self.data.items():
            p_node = QTreeWidgetItem(self.tree)
            p_node.setText(0, f"📦 {proj_name}")
            p_node.setData(0, Qt.ItemDataRole.UserRole, proj_name) 
            p_node.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            p_node.setForeground(0, QColor("#cdd6f4"))
            
            std_order = ["Mission","Payload","AOCS","EPS","TCS","COMMS","OBDH","Structure"]
            sorted_keys = sorted(subsystems.keys(), key=lambda x: std_order.index(x) if x in std_order else 99)
            
            for sub in sorted_keys:
                s_node = QTreeWidgetItem(p_node)
                s_node.setText(0, f"{sub} ({len(subsystems[sub])})")
                s_node.setData(0, Qt.ItemDataRole.UserRole, sub)
                s_node.setForeground(0, QColor("#a6adc8"))
            
            p_node.setExpanded(True)

    def on_tree_click(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if item.parent(): # Is Subsystem
            self.current_project = item.parent().data(0, Qt.ItemDataRole.UserRole)
            self.current_subsystem = data
            self.lbl_title.setText(f"{self.current_project}  /  {self.current_subsystem}")
            
            # --- ENABLE TOOLS ---
            self.btn_nr.setEnabled(True)
            self.search.setEnabled(True)
            self.filter_type.setEnabled(True) # Enable Filter
            
            self.btn_ep.setEnabled(False); self.btn_dp.setEnabled(False)
            self.btn_add_sub.setEnabled(False); self.btn_del_sub.setEnabled(True) # Enable Delete Sub
            self.load_table()
        else: # Is Project
            self.current_project = data
            self.current_subsystem = None
            self.lbl_title.setText(f"Project: {self.current_project}")
            self.table.setRowCount(0)
            
            # --- DISABLE TOOLS ---
            self.btn_nr.setEnabled(False)
            self.search.setEnabled(False)
            self.filter_type.setEnabled(False) # Disable Filter
            
            self.btn_ep.setEnabled(True); self.btn_dp.setEnabled(True)
            self.btn_add_sub.setEnabled(True); self.btn_del_sub.setEnabled(False) # Enable Add Sub

    def load_table(self):
        if not self.current_project or not self.current_subsystem: return
        self.table.setSortingEnabled(False) 
        reqs = self.data[self.current_project][self.current_subsystem]
        self.table.setRowCount(len(reqs))
        
        for i, r in enumerate(reqs):
            self.table.setItem(i, 0, QTableWidgetItem(r['id']))
            self.table.setItem(i, 1, QTableWidgetItem(r.get('type', '-')))
            
            doc = QTextDocument(); doc.setHtml(r.get('desc', ''))
            plain_text = doc.toPlainText() 
            self.table.setItem(i, 2, QTableWidgetItem(plain_text))
            
            self.table.setItem(i, 3, QTableWidgetItem(str(r.get('value', ''))))
            self.table.setItem(i, 4, QTableWidgetItem(str(r.get('unit', ''))))
            self.table.setItem(i, 5, QTableWidgetItem(r.get('status', '')))
            self.table.setItem(i, 6, QTableWidgetItem(r.get('method', '')))
            self.table.setItem(i, 7, QTableWidgetItem(r.get('parent_id', '')))
            
            self.color_row(i, r)
            
        self.table.setSortingEnabled(True)
        self.table.resizeRowsToContents() 
        
        # Apply filters immediately after loading
        self.apply_filter()

    def color_row(self, row, req):
        st = req.get('status', '')
        review = req.get('needs_review', False)
        
        default_bg = QColor("#252535") 
        default_fg = QColor("white")
        
        stat_fg = default_fg
        
        if review:
            stat_fg = QColor("#FFFF00") # Yellow
        elif "Verified" in st:
            stat_fg = QColor("#a6e3a1") # Green
        elif "TBD" in st or "TBC" in st:
            stat_fg = QColor("#f38ba8") # Red/Pink
        elif "Closed" in st:
            stat_fg = QColor("#6c7086") # Grey

        for c in range(8):
            it = self.table.item(row, c)
            it.setBackground(default_bg)
            it.setForeground(default_fg)
            if c == 5:
                it.setForeground(stat_fg)

    def apply_filter(self, _=None):
        search_text = self.search.text().lower()
        filter_type = self.filter_type.currentText()
        
        for r in range(self.table.rowCount()):
            # 1. Text Search Logic
            match_text = False
            if (search_text in self.table.item(r, 0).text().lower() or 
                search_text in self.table.item(r, 2).text().lower() or
                search_text in self.table.item(r, 7).text().lower()):
                match_text = True
            
            # 2. Type Filter Logic
            match_type = False
            row_type = self.table.item(r, 1).text()
            if filter_type == "All Types" or row_type == filter_type:
                match_type = True

            # Combined Logic
            self.table.setRowHidden(r, not (match_text and match_type))

    # --- ACTIONS ---
    def add_project(self):
        d = NewProjectDialog(self)
        if d.exec():
            name, is_std, sub = d.get_data()
            if not name: return
            if name in self.data:
                QMessageBox.warning(self, "Error", "Project already exists!")
                return
            
            if is_std:
                self.data[name] = {k:[] for k in ["Mission","Payload","AOCS","EPS","TCS","COMMS","OBDH","Structure"]}
            else:
                self.data[name] = {sub: []}
            
            self.refresh_tree()
            self.save_database()

    def add_subsystem(self):
        if not self.current_project: return
        new_sub, ok = QInputDialog.getText(self, "New Subsystem", "Name (e.g. Ground Segment):")
        if ok and new_sub:
            if new_sub in self.data[self.current_project]:
                QMessageBox.warning(self,"Error", "Subsystem exists.")
            else:
                self.data[self.current_project][new_sub] = []
                self.refresh_tree()
                self.save_database()

    def delete_subsystem(self):
        if not self.current_project or not self.current_subsystem: return
        
        req_count = len(self.data[self.current_project][self.current_subsystem])
        msg = f"Are you sure you want to delete subsystem '{self.current_subsystem}'?"
        if req_count > 0:
            msg += f"\n\nWARNING: It contains {req_count} requirements!\nThey will be permanently deleted."
            
        if QMessageBox.question(self, "Delete Subsystem", msg, QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.data[self.current_project][self.current_subsystem]
            self.save_database()
            self.refresh_tree()
            self.lbl_title.setText("Subsystem Deleted")
            self.table.setRowCount(0)

    def add_requirement(self):
        all_ids = self.get_all_ids_in_project(self.current_project)
        d = RequirementDialog(self, all_ids)
        if d.exec():
            new_req = d.get_data()
            self.data[self.current_project][self.current_subsystem].append(new_req)
            self.save_database()
            self.load_table()
            self.refresh_tree() 

    def edit_requirement(self):
        r = self.table.currentRow()
        if r < 0: return
        
        req_id = self.table.item(r, 0).text()
        req_list = self.data[self.current_project][self.current_subsystem]
        real_req = next((x for x in req_list if x['id'] == req_id), None)
        
        if not real_req: return 

        all_ids = self.get_all_ids_in_project(self.current_project)
        d = RequirementDialog(self, all_ids, real_req)
        
        if d.exec():
            new_data = d.get_data()
            if new_data['id'] != real_req['id']:
                self.update_parent_references(real_req['id'], new_data['id'])
            real_req.update(new_data)
            self.save_database()
            self.load_table()

    def delete_requirement(self):
        r = self.table.currentRow()
        if r < 0: return
        req_id = self.table.item(r, 0).text()
        
        orphans = self.check_orphans(req_id)
        msg = f"Delete '{req_id}'?"
        if orphans:
            msg += f"\n\nWARNING: This requirement is parent to {len(orphans)} items!\n(e.g. {orphans[:3]}).\nChildren will be orphaned."
            
        if QMessageBox.question(self, "Delete", msg, QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            req_list = self.data[self.current_project][self.current_subsystem]
            self.data[self.current_project][self.current_subsystem] = [x for x in req_list if x['id'] != req_id]
            self.save_database()
            self.load_table()
            self.refresh_tree()

    def rename_project(self):
        if not self.current_project: return
        new_n, ok = QInputDialog.getText(self, "Rename", "New name:", text=self.current_project)
        if ok and new_n and new_n != self.current_project:
            if new_n in self.data: return
            self.data[new_n] = self.data.pop(self.current_project)
            self.save_database()
            self.refresh_tree()

    def delete_project(self):
        if not self.current_project: return
        if QMessageBox.question(self, "Delete", f"Delete project '{self.current_project}'?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.data[self.current_project]
            self.save_database()
            self.refresh_tree()
            self.lbl_title.setText("No Selection")
            self.table.setRowCount(0)

    # --- PERSISTENCE ---
    def check_and_load_startup(self):
        lp = None
        if os.path.exists(CONFIG_FILE):
            try: 
                with open(CONFIG_FILE,'r') as f: lp = json.load(f).get("last_db_path")
            except: pass
        
        if lp and os.path.exists(lp):
            self.db_path = lp; self.load_database()
        else:
            d = StartupDialog(self)
            if d.exec():
                if d.choice=="OPEN": self.open_existing_db_dialog()
                elif d.choice=="NEW": self.create_new_db_dialog()

    def save_database(self):
        if self.db_path:
            with open(self.db_path, 'w') as f: json.dump(self.data, f, indent=4)
            with open(CONFIG_FILE, 'w') as f: json.dump({"last_db_path": self.db_path}, f)

    def load_database(self):
        try:
            with open(self.db_path, 'r') as f: self.data = json.load(f)
            self.refresh_tree()
            self.setWindowTitle(f"SatReq Manager {VERSION} - {os.path.basename(self.db_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot load DB:\n{e}")

    def open_existing_db_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open DB", "", "JSON (*.json)")
        if p: self.db_path = p; self.load_database(); self.save_database()

    def create_new_db_dialog(self):
        p, _ = QFileDialog.getSaveFileName(self, "New DB", "", "JSON (*.json)")
        if p: self.db_path = p; self.data = {}; self.save_database(); self.load_database()

    # --- EXPORT ---
    def export_csv(self):
        if not self.current_project: return
        p, _ = QFileDialog.getSaveFileName(self, "Export CSV", f"{self.current_project}.csv", "CSV (*.csv)")
        if p:
            try:
                with open(p, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(["Project", "Subsystem", "ID", "Type", "Description", "Value", "Unit", "Status", "Parent", "Last Mod"])
                    for sub, reqs in self.data[self.current_project].items():
                        for r in reqs:
                            plain = QTextDocument(); plain.setHtml(r.get('desc',''))
                            w.writerow([
                                self.current_project, sub, r['id'], r.get('type',''), 
                                plain.toPlainText(), r.get('value',''), r.get('unit',''), 
                                r.get('status',''), r.get('parent_id',''), r.get('last_modified','')
                            ])
                QMessageBox.information(self, "Export", "CSV Saved.")
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def export_pdf(self):
        if not self.current_project: return
        fn, _ = QFileDialog.getSaveFileName(self, "Export PDF", f"{self.current_project}.pdf", "PDF (*.pdf)")
        if not fn: return

        html = f"""<html><head><style>
            body {{ font-family: sans-serif; }} h1 {{ color: #2c3e50; }} h2 {{ color: #e67e22; border-bottom: 2px solid #e67e22; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
            th {{ background: #34495e; color: white; padding: 6px; }} td {{ border: 1px solid #ccc; padding: 6px; }}
            .verified {{ color: green; font-weight:bold; }} .tbd {{ color: red; }}
        </style></head><body><h1>Project: {self.current_project}</h1><p>Generated: {get_timestamp()}</p>"""

        for sub, reqs in self.data[self.current_project].items():
            if not reqs: continue
            html += f"<h2>{sub}</h2><table><thead><tr><th>ID</th><th>Type</th><th>Description</th><th>Target</th><th>Status</th><th>Parent</th></tr></thead><tbody>"
            for r in reqs:
                st_class = "verified" if "Verified" in r['status'] else ("tbd" if "TBD" in r['status'] else "")
                html += f"<tr><td><b>{r['id']}</b></td><td>{r.get('type','-')}</td><td>{r.get('desc','')}</td><td>{r.get('value','')} {r.get('unit','')}</td><td class='{st_class}'>{r['status']}</td><td>{r.get('parent_id','')}</td></tr>"
            html += "</tbody></table>"
        
        html += "</body></html>"
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fn)
        doc = QTextDocument(); doc.setHtml(html); doc.print(printer)
        QMessageBox.information(self, "OK", "PDF Saved.")

    def context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        r = item.row()
        req_id = self.table.item(r, 0).text()
        
        m = QMenu()
        act_child = QAction(f"View children of {req_id}", self)
        
        children = []
        for s_name, s_reqs in self.data[self.current_project].items():
            for x in s_reqs:
                if x.get('parent_id') == req_id:
                    copy_x = x.copy(); copy_x['subsystem'] = s_name
                    children.append(copy_x)
        
        act_child.setEnabled(len(children) > 0)
        act_child.triggered.connect(lambda: ChildrenViewDialog(self, req_id, children).exec())
        m.addAction(act_child)
        m.exec(self.table.viewport().mapToGlobal(pos))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = SatReqManager()
    w.showMaximized()
    sys.exit(app.exec())