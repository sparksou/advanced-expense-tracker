import csv
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

APP_TITLE = "Advanced Expense Tracker"
DB_FILE = "advanced_expenses.db"

LIGHT = {
    "bg": "#f4f7fb",
    "card": "#ffffff",
    "text": "#172033",
    "muted": "#64748b",
    "accent": "#4f46e5",
    "accent_dark": "#3730a3",
    "green": "#16a34a",
    "red": "#dc2626",
    "orange": "#ea580c",
    "border": "#dbe3ef",
    "input": "#ffffff",
    "selected": "#e0e7ff",
}

DARK = {
    "bg": "#0f172a",
    "card": "#172033",
    "text": "#f8fafc",
    "muted": "#94a3b8",
    "accent": "#818cf8",
    "accent_dark": "#6366f1",
    "green": "#22c55e",
    "red": "#ef4444",
    "orange": "#fb923c",
    "border": "#334155",
    "input": "#1e293b",
    "selected": "#312e81",
}


class AdvancedExpenseTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x840")
        self.root.minsize(1100, 720)
        
        self.theme_name = "Light"
        self.colors = LIGHT.copy()
        
        # Typography hierarchy
        self.font_title = ("Segoe UI", 22, "bold")
        self.font_header = ("Segoe UI", 11, "bold")
        self.font_body = ("Segoe UI", 10)
        self.font_small = ("Segoe UI", 9)
        self.font_card_value = ("Segoe UI", 16, "bold")
        self.font_card_label = ("Segoe UI", 9, "bold")

        # Database initialization
        self.conn = sqlite3.connect(DB_FILE)
        self.cursor = self.conn.cursor()
        self.init_db()

        self.currency_symbol = self.get_setting("currency", "$")
        self.monthly_budget = float(self.get_setting("budget", "1000.0"))
        
        self.category_values = [
            "Food", "Transport", "Utilities", "Entertainment",
            "Shopping", "Health", "Education", "Bills", "Other"
        ]

        # Sorting state tracker
        self.sort_column = "date"
        self.sort_reverse = True

        self.build_ui()
        self.apply_theme()
        self.load_expenses()
        self.refresh_dashboard()

        # Key Bindings
        self.root.bind("<Escape>", lambda e: self.clear_form())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- DATABASE METHODS ----------------
    def init_db(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def get_setting(self, key, default):
        self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = self.cursor.fetchone()
        if row:
            return row[0]
        self.cursor.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
            (key, default),
        )
        self.conn.commit()
        return default

    def set_setting(self, key, value):
        self.cursor.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
            (key, str(value)),
        )
        self.conn.commit()

    # ---------------- UI BUILDERS ----------------
    def make_button(self, parent, text, command, bg=None, fg="white", width=None):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font_header,
            bg=bg or self.colors["accent"],
            fg=fg,
            activebackground=self.colors["accent_dark"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            width=width,
        )

    def build_ui(self):
        # Header Frame
        self.header = tk.Frame(self.root)
        self.header.pack(fill="x")

        header_inner = tk.Frame(self.header)
        header_inner.pack(fill="x", padx=24, pady=16)

        title_box = tk.Frame(header_inner)
        title_box.pack(side="left")

        self.title_label = tk.Label(title_box, text="💰 Expense Tracker Pro", font=self.font_title)
        self.title_label.pack(anchor="w")
        self.subtitle_label = tk.Label(
            title_box,
            text="Seamless spending intelligence and budget control.",
            font=self.font_body,
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header_inner)
        actions.pack(side="right", anchor="n")

        tk.Label(actions, text="Currency", font=self.font_small).pack(side="left", padx=(0, 4))
        self.currency_selector = ttk.Combobox(
            actions,
            values=["$", "€", "£", "₹", "¥", "A$", "C$", "R$", "₩", "₱", "₦"],
            width=4,
            state="readonly",
        )
        self.currency_selector.set(self.currency_symbol)
        self.currency_selector.pack(side="left", padx=(0, 10))
        self.currency_selector.bind("<<ComboboxSelected>>", self.change_currency)

        tk.Label(actions, text="Budget", font=self.font_small).pack(side="left", padx=(0, 4))
        self.budget_var = tk.StringVar(value=str(self.monthly_budget))
        self.budget_entry = ttk.Entry(actions, textvariable=self.budget_var, width=7)
        self.budget_entry.pack(side="left", padx=(0, 10))
        self.budget_entry.bind("<Return>", self.update_budget)

        self.theme_button = self.make_button(actions, "🌙 Dark", self.toggle_theme)
        self.theme_button.pack(side="left")

        # Dashboard Metric Cards
        self.cards_frame = tk.Frame(self.root)
        self.cards_frame.pack(fill="x", padx=24, pady=(2, 14))
        self.card_widgets = {}
        for key, label, icon in [
            ("month", "THIS MONTH", "📅"),
            ("today", "TODAY", "☀️"),
            ("budget_status", "BUDGET LEFT", "🎯"),
            ("average", "AVG EXPENSE", "📌"),
        ]:
            card = tk.Frame(self.cards_frame, bd=1, relief="solid")
            card.pack(side="left", fill="both", expand=True, padx=4)
            top = tk.Frame(card)
            top.pack(fill="x", padx=12, pady=(10, 2))
            label_widget = tk.Label(top, text=f"{icon}  {label}", font=self.font_card_label)
            label_widget.pack(anchor="w")
            value_widget = tk.Label(card, text="0", font=self.font_card_value)
            value_widget.pack(anchor="w", padx=12, pady=(0, 10))
            self.card_widgets[key] = (card, top, label_widget, value_widget)

        # Input / Edit Form Frame
        self.input_card = tk.LabelFrame(
            self.root,
            text=" Record New Expense ",
            font=self.font_header,
            bd=1,
            relief="solid",
            padx=12,
            pady=10,
        )
        self.input_card.pack(fill="x", padx=24, pady=(0, 12))

        self.date_var = tk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar(value=self.category_values[0])
        self.description_var = tk.StringVar()
        self.editing_id = None

        self.create_labeled_entry(self.input_card, "Date", self.date_var, 0, 0, 14)
        self.create_labeled_entry(self.input_card, "Amount", self.amount_var, 0, 2, 12)

        tk.Label(self.input_card, text="Category", font=self.font_body).grid(
            row=0, column=4, padx=(10, 4), pady=4, sticky="w"
        )
        self.category_combo = ttk.Combobox(
            self.input_card,
            textvariable=self.category_var,
            values=self.category_values,
            width=15,
            state="readonly",
        )
        self.category_combo.grid(row=0, column=5, padx=4, pady=4, sticky="w")

        desc_entry = self.create_labeled_entry(self.input_card, "Description", self.description_var, 0, 6, 28)
        desc_entry.bind("<Return>", lambda e: self.save_expense())

        self.save_button = self.make_button(self.input_card, "➕ Add Expense", self.save_expense, self.colors["green"])
        self.save_button.grid(row=1, column=1, columnspan=2, padx=4, pady=6, sticky="w")
        self.clear_button = self.make_button(self.input_card, "↺ Clear", self.clear_form, self.colors["muted"])
        self.clear_button.grid(row=1, column=3, padx=4, pady=6, sticky="w")

        # Filters & Search Toolbar
        self.filter_frame = tk.Frame(self.root)
        self.filter_frame.pack(fill="x", padx=24, pady=(0, 8))

        tk.Label(self.filter_frame, text="🔎 Search", font=self.font_header).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.load_expenses())
        self.search_entry = ttk.Entry(self.filter_frame, textvariable=self.search_var, width=26)
        self.search_entry.pack(side="left", padx=(0, 10))

        tk.Label(self.filter_frame, text="Category", font=self.font_body).pack(side="left", padx=(0, 4))
        self.filter_category_var = tk.StringVar(value="All")
        self.filter_category = ttk.Combobox(
            self.filter_frame,
            textvariable=self.filter_category_var,
            values=["All"] + self.category_values,
            width=14,
            state="readonly",
        )
        self.filter_category.pack(side="left", padx=(0, 10))
        self.filter_category.bind("<<ComboboxSelected>>", lambda e: self.load_expenses())

        tk.Label(self.filter_frame, text="Month", font=self.font_body).pack(side="left", padx=(0, 4))
        self.filter_month_var = tk.StringVar(value="All")
        months = ["All"] + [f"{m:02d}" for m in range(1, 13)]
        self.filter_month = ttk.Combobox(
            self.filter_frame,
            textvariable=self.filter_month_var,
            values=months,
            width=8,
            state="readonly",
        )
        self.filter_month.pack(side="left", padx=(0, 10))
        self.filter_month.bind("<<ComboboxSelected>>", lambda e: self.load_expenses())

        self.reset_button = self.make_button(self.filter_frame, "✕ Reset Filters", self.reset_filters, self.colors["orange"])
        self.reset_button.pack(side="left")

        # Main Table / Treeview with Sort Headers
        self.table_frame = tk.Frame(self.root, bd=1, relief="solid")
        self.table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 10))

        columns = ("ID", "Date", "Amount", "Category", "Description")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", selectmode="extended")
        
        headings_config = {
            "ID": ("ID #", 60, "id"),
            "Date": ("Date ↕", 120, "date"),
            "Amount": ("Amount ↕", 130, "amount"),
            "Category": ("Category ↕", 150, "category"),
            "Description": ("Description ↕", 440, "description"),
        }
        
        for col, (text, width, sort_key) in headings_config.items():
            self.tree.heading(col, text=text, command=lambda c=sort_key: self.sort_table(c))
            self.tree.column(col, width=width, anchor="center")
        self.tree.column("Description", anchor="w")

        yscroll = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self.table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_expense())

        # Action Control Panel (Bottom)
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(fill="x", padx=24, pady=(0, 14))

        left_actions = tk.Frame(self.control_frame)
        left_actions.pack(side="left")
        for text, command, color in [
            ("☑ Select All", self.select_all, self.colors["muted"]),
            ("✏ Edit Selected", self.edit_selected, self.colors["accent"]),
            ("🗑 Delete Selected", self.delete_expense, self.colors["red"]),
            ("⚠ Clear All", self.delete_all, "#991b1b"),
        ]:
            self.make_button(left_actions, text, command, color).pack(side="left", padx=2)

        right_actions = tk.Frame(self.control_frame)
        right_actions.pack(side="right")
        for text, command, color in [
            ("📊 Analytics", self.show_chart, self.colors["accent"]),
            ("💾 Export CSV", self.export_csv, self.colors["orange"]),
            ("🔗 Share Summary", self.share_summary, "#7c3aed"),
        ]:
            self.make_button(right_actions, text, command, color).pack(side="left", padx=2)

        self.status_label = tk.Label(self.root, text="System Ready", font=self.font_small, anchor="w")
        self.status_label.pack(fill="x", padx=26, pady=(0, 6))

    def create_labeled_entry(self, parent, label, variable, row, col, width):
        tk.Label(parent, text=label, font=self.font_body).grid(
            row=row, column=col, padx=(10 if col else 4, 4), pady=4, sticky="w"
        )
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=col + 1, padx=4, pady=4, sticky="w")
        return entry

    # ---------------- THEME & STYLING ----------------
    def apply_theme(self):
        self.colors = DARK.copy() if self.theme_name == "Dark" else LIGHT.copy()
        self.root.configure(bg=self.colors["bg"])
        
        for frame in [self.header, self.cards_frame, self.input_card, self.filter_frame, self.table_frame, self.control_frame]:
            frame.configure(bg=self.colors["bg"] if frame != self.header else self.colors["card"])

        self.title_label.configure(bg=self.colors["card"], fg=self.colors["text"])
        self.subtitle_label.configure(bg=self.colors["card"], fg=self.colors["muted"])
        self.input_card.configure(bg=self.colors["card"], fg=self.colors["text"])
        self.table_frame.configure(bg=self.colors["card"])
        self.status_label.configure(bg=self.colors["bg"], fg=self.colors["muted"])

        self.style_widgets()
        for card, top, label, value in self.card_widgets.values():
            card.configure(bg=self.colors["card"], highlightbackground=self.colors["border"])
            top.configure(bg=self.colors["card"])
            label.configure(bg=self.colors["card"], fg=self.colors["muted"])
            value.configure(bg=self.colors["card"], fg=self.colors["text"])

        self.theme_button.configure(
            text="☀ Light" if self.theme_name == "Dark" else "🌙 Dark",
            bg=self.colors["accent"],
            activebackground=self.colors["accent_dark"],
        )
        self.root.update_idletasks()

    def style_widgets(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "TEntry",
            fieldbackground=self.colors["input"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            padding=5,
        )
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["input"],
            background=self.colors["input"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            padding=4,
        )
        style.configure(
            "Treeview",
            background=self.colors["card"],
            fieldbackground=self.colors["card"],
            foreground=self.colors["text"],
            rowheight=32,
            bordercolor=self.colors["border"],
            font=self.font_body,
        )
        style.map(
            "Treeview",
            background=[("selected", self.colors["selected"])],
            foreground=[("selected", self.colors["text"])],
        )
        style.configure(
            "Treeview.Heading",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=self.font_header,
            padding=6,
        )
        style.map("Treeview.Heading", background=[("active", self.colors["border"])])

    def toggle_theme(self):
        self.theme_name = "Dark" if self.theme_name == "Light" else "Light"
        self.apply_theme()
        self.status_label.configure(text=f"Switched to {self.theme_name} theme.")

    # ---------------- BUSINESS LOGIC & CRUD ----------------
    def validate_form(self):
        date_val = self.date_var.get().strip()
        amount_text = self.amount_var.get().strip()
        category = self.category_var.get().strip()
        description = self.description_var.get().strip()

        if not date_val or not amount_text or not category:
            messagebox.showerror("Validation Error", "Date, amount, and category fields are mandatory.")
            return None

        try:
            datetime.strptime(date_val, "%Y-%m-%d")
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation Error", "Please provide a valid YYYY-MM-DD date and a positive number amount.")
            return None

        return date_val, amount, category, description

    def save_expense(self):
        result = self.validate_form()
        if not result:
            return
        date_val, amount, category, description = result

        if self.editing_id is None:
            self.cursor.execute(
                "INSERT INTO expenses(date, amount, category, description) VALUES (?, ?, ?, ?)",
                (date_val, amount, category, description),
            )
            msg = "Expense successfully recorded."
        else:
            self.cursor.execute(
                "UPDATE expenses SET date=?, amount=?, category=?, description=? WHERE id=?",
                (date_val, amount, category, description, self.editing_id),
            )
            msg = f"Expense #{self.editing_id} successfully updated."

        self.conn.commit()
        self.clear_form()
        self.load_expenses()
        self.refresh_dashboard()
        self.status_label.configure(text=msg)

    def clear_form(self):
        self.editing_id = None
        self.date_var.set(datetime.today().strftime("%Y-%m-%d"))
        self.amount_var.set("")
        self.category_var.set(self.category_values[0])
        self.description_var.set("")
        self.save_button.configure(text="➕ Add Expense", bg=self.colors["green"])

    def edit_selected(self):
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Edit Selection", "Please select exactly one expense entry to edit.")
            return
        item = selected[0]
        values = self.tree.item(item, "values")
        self.editing_id = int(values[0])
        self.date_var.set(values[1])
        self.amount_var.set(values[2].replace(self.currency_symbol, "").replace(",", ""))
        self.category_var.set(values[3])
        self.description_var.set(values[4])
        self.save_button.configure(text="💾 Update Expense", bg=self.colors["accent"])
        self.status_label.configure(text=f"Editing expense #{self.editing_id}. Modify values above and click Update.")

    def delete_expense(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Deletion", "Select at least one expense record to delete.")
            return
        count = len(selected)
        if not messagebox.askyesno("Confirm Deletion", f"Permanently delete {count} selected item(s)?"):
            return
        
        for item in selected:
            exp_id = self.tree.item(item, "values")[0]
            self.cursor.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
        self.conn.commit()
        
        self.load_expenses()
        self.refresh_dashboard()
        self.status_label.configure(text=f"Successfully deleted {count} item(s).")

    def delete_all(self):
        self.cursor.execute("SELECT COUNT(*) FROM expenses")
        count = self.cursor.fetchone()[0]
        if count == 0:
            messagebox.showinfo("Empty Log", "No expense records found.")
            return
        if not messagebox.askyesno("⚠ Danger Zone", f"This will wipe all {count} expense entries permanently. Proceed?", icon="warning"):
            return
        
        self.cursor.execute("DELETE FROM expenses")
        self.conn.commit()
        self.clear_form()
        self.load_expenses()
        self.refresh_dashboard()
        self.status_label.configure(text="All database expense records have been wiped.")

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())
        self.status_label.configure(text="All visible table rows selected.")

    # ---------------- SORTING & FILTERING ----------------
    def sort_table(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.load_expenses()

    def load_expenses(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip().lower()
        category_filter = self.filter_category_var.get()
        month_filter = self.filter_month_var.get()
        current_year = datetime.today().strftime("%Y")

        query = "SELECT id, date, amount, category, description FROM expenses"
        clauses = []
        params = []

        if search:
            clauses.append("(LOWER(category) LIKE ? OR LOWER(description) LIKE ? OR LOWER(date) LIKE ?)")
            token = f"%{search}%"
            params.extend([token, token, token])
        if category_filter != "All":
            clauses.append("category = ?")
            params.append(category_filter)
        if month_filter != "All":
            clauses.append("strftime('%Y-%m', date) = ?")
            params.append(f"{current_year}-{month_filter}")

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
            
        # Map sorting keys to SQL columns
        sort_map = {
            "id": "id",
            "date": "date",
            "amount": "amount",
            "category": "category",
            "description": "description"
        }
        col_sql = sort_map.get(self.sort_column, "date")
        direction = "DESC" if self.sort_reverse else "ASC"
        query += f" ORDER BY {col_sql} {direction}, id DESC"

        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()

        for row in rows:
            amt_formatted = f"{self.currency_symbol}{row[2]:,.2f}"
            self.tree.insert("", tk.END, values=(row[0], row[1], amt_formatted, row[3], row[4] or ""))

        self.status_label.configure(text=f"Loaded {len(rows)} expense record(s).")

    def reset_filters(self):
        self.search_var.set("")
        self.filter_category_var.set("All")
        self.filter_month_var.set("All")
        self.sort_column = "date"
        self.sort_reverse = True
        self.load_expenses()

    # ---------------- DASHBOARD & METRICS ----------------
    def refresh_dashboard(self):
        today = datetime.today().strftime("%Y-%m-%d")
        month_prefix = datetime.today().strftime("%Y-%m")

        self.cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date LIKE ?", (f"{month_prefix}%",))
        month_total = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date = ?", (today,))
        today_total = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COALESCE(AVG(amount),0) FROM expenses")
        average = self.cursor.fetchone()[0]

        budget_remaining = self.monthly_budget - month_total

        self.card_widgets["month"][3].configure(text=f"{self.currency_symbol}{month_total:,.2f}")
        self.card_widgets["today"][3].configure(text=f"{self.currency_symbol}{today_total:,.2f}")
        self.card_widgets["budget_status"][3].configure(
            text=f"{self.currency_symbol}{budget_remaining:,.2f}",
            fg=self.colors["red"] if budget_remaining < 0 else self.colors["green"]
        )
        self.card_widgets["average"][3].configure(text=f"{self.currency_symbol}{average:,.2f}")

    def update_budget(self, _event=None):
        try:
            val = float(self.budget_var.get().strip())
            if val < 0:
                raise ValueError
            self.monthly_budget = val
            self.set_setting("budget", val)
            self.refresh_dashboard()
            self.status_label.configure(text=f"Monthly budget updated to {self.currency_symbol}{val:,.2f}.")
        except ValueError:
            messagebox.showerror("Invalid Budget", "Please enter a valid positive numerical budget value.")
            self.budget_var.set(str(self.monthly_budget))

    def change_currency(self, _event=None):
        self.currency_symbol = self.currency_selector.get()
        self.set_setting("currency", self.currency_symbol)
        self.load_expenses()
        self.refresh_dashboard()
        self.status_label.configure(text=f"Currency symbol updated to {self.currency_symbol}.")

    # ---------------- ANALYTICS & CHARTS ----------------
    def show_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Module Missing", "Matplotlib is required for charts.\n\nInstall via: pip install matplotlib")
            return

        month_prefix = datetime.today().strftime("%Y-%m")
        self.cursor.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE date LIKE ? GROUP BY category ORDER BY SUM(amount) DESC",
            (f"{month_prefix}%",),
        )
        category_data = self.cursor.fetchall()

        self.cursor.execute(
            "SELECT date, SUM(amount) FROM expenses WHERE date LIKE ? GROUP BY date ORDER BY date",
            (f"{month_prefix}%",),
        )
        daily_data = self.cursor.fetchall()

        if not category_data:
            messagebox.showinfo("Analytics", "No expenses recorded for the current month yet.")
            return

        win = tk.Toplevel(self.root)
        win.title("Spending Analytics")
        win.geometry("1100x640")
        win.configure(bg=self.colors["bg"])

        toolbar = tk.Frame(win, bg=self.colors["bg"])
        toolbar.pack(fill="x", padx=16, pady=12)
        tk.Label(
            toolbar,
            text=f"📊 Analytics Dashboard — {datetime.today().strftime('%B %Y')}",
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["text"],
        ).pack(side="left")

        fig = plt.Figure(figsize=(10.5, 5.2), dpi=100, facecolor=self.colors["card"])
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        labels = [row[0] for row in category_data]
        values = [row[1] for row in category_data]
        ax1.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, wedgeprops={"edgecolor": "white"})
        ax1.set_title("Category Breakdown", fontweight="bold")

        dates = [row[0][-5:] for row in daily_data]
        day_values = [row[1] for row in daily_data]
        ax2.bar(dates, day_values, color=self.colors["accent"])
        ax2.set_title("Daily Spending Volume", fontweight="bold")
        ax2.set_xlabel("Date")
        ax2.set_ylabel(f"Amount ({self.currency_symbol})")
        ax2.tick_params(axis="x", rotation=45)
        fig.tight_layout(pad=3)

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=14, pady=14)

        close_btn = self.make_button(win, "Close Analytics", win.destroy, self.colors["muted"])
        close_btn.pack(pady=(0, 14))

    # ---------------- EXPORT & SHARING ----------------
    def export_csv(self):
        file_path = filedialog.asksaveasfilename(
            title="Export Expense Data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="expense_export.csv",
        )
        if not file_path:
            return

        self.cursor.execute("SELECT id, date, amount, category, description FROM expenses ORDER BY date DESC")
        rows = self.cursor.fetchall()
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "Date", "Amount", "Category", "Description"])
                writer.writerows(rows)
            messagebox.showinfo("Export Successful", f"Successfully exported {len(rows)} records to:\n{file_path}")
            self.status_label.configure(text="CSV data export completed.")
        except OSError as exc:
            messagebox.showerror("Export Failed", f"Could not save file.\n\n{exc}")

    def share_summary(self):
        month_prefix = datetime.today().strftime("%Y-%m")
        month_name = datetime.today().strftime("%B %Y")
        self.cursor.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE date LIKE ? GROUP BY category ORDER BY SUM(amount) DESC",
            (f"{month_prefix}%",),
        )
        rows = self.cursor.fetchall()
        if not rows:
            messagebox.showinfo("Summary", "No expense records found for this month.")
            return

        total = sum(row[1] for row in rows)
        report = [
            f"📊 Expense Summary — {month_name}",
            f"Total Spent: {self.currency_symbol}{total:,.2f}",
            f"Monthly Budget: {self.currency_symbol}{self.monthly_budget:,.2f}",
            "",
            "Breakdown:",
        ]
        report.extend(f"• {cat}: {self.currency_symbol}{amt:,.2f}" for cat, amt in rows)
        report.append("")
        report.append("Generated with Expense Tracker Pro")
        text = "\n".join(report)

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        messagebox.showinfo("Clipboard Copied", "Monthly summary text copied to clipboard successfully.")

    def on_close(self):
        try:
            self.conn.commit()
            self.conn.close()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AdvancedExpenseTrackerApp(root)
    root.mainloop()