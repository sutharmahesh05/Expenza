import sqlite3
from collections import defaultdict
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

class User:
    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class Expense:
    def __init__(self, id, user_id, category, amount, description, date):
        self.id = id
        self.user_id = user_id
        self.category = category
        self.amount = amount
        self.description = description
        self.date = date

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'amount': self.amount,
            'description': self.description,
            'date': self.date.isoformat() if isinstance(self.date, datetime) else self.date
        }

class Budget:
    def __init__(self, id, user_id, category, amount):
        self.id = id
        self.user_id = user_id
        self.category = category
        self.amount = amount

class ExpenseManager:
    def __init__(self):
        self.conn = sqlite3.connect('expenses.db', check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                date TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        self.conn.commit()

    def add_user(self, username, email, password):
        cursor = self.conn.cursor()
        password_hash = generate_password_hash(password)
        try:
            cursor.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                           (username, email, password_hash))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_by_id(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            return User(*user_data)
        return None

    def get_user_by_username(self, username):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        if user_data:
            return User(*user_data)
        return None

    def get_user_by_email(self, email):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        if user_data:
            return User(*user_data)
        return None

    def add_expense(self, user_id, category, amount, description):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO expenses (user_id, category, amount, description, date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, category, amount, description, datetime.now()))
        self.conn.commit()
        return Expense(cursor.lastrowid, user_id, category, amount, description, datetime.now())

    def get_user_expenses(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC', (user_id,))
        return [Expense(*row) for row in cursor.fetchall()]

    def set_budget(self, user_id, category, amount):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO budgets (user_id, category, amount)
            VALUES (?, ?, ?)
        ''', (user_id, category, amount))
        self.conn.commit()

    def get_user_budgets(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM budgets WHERE user_id = ?', (user_id,))
        return [Budget(*row) for row in cursor.fetchall()]

    def delete_expense(self, expense_id, user_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, user_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_monthly_expenses(self, user_id, year):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT strftime('%m', date) as month, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND strftime('%Y', date) = ?
            GROUP BY month
            ORDER BY month
        ''', (user_id, str(year)))
        return cursor.fetchall()

    def get_yearly_expenses(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT strftime('%Y', date) as year, SUM(amount) as total
            FROM expenses
            WHERE user_id = ?
            GROUP BY year
            ORDER BY year
        ''', (user_id,))
        return cursor.fetchall()

    def analyze_user_expenses(self, user_id):
        expenses = self.get_user_expenses(user_id)
        budgets = self.get_user_budgets(user_id)
        total_spent = sum(expense.amount for expense in expenses)
        category_totals = defaultdict(float)
        for expense in expenses:
            category_totals[expense.category] += expense.amount

        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        budget_status = {}
        for budget in budgets:
            spent = category_totals.get(budget.category, 0)
            budget_status[budget.category] = {
                'budget': budget.amount,
                'spent': spent,
                'remaining': budget.amount - spent
            }

        monthly_expenses = self.get_monthly_expenses(user_id, datetime.now().year)
        yearly_expenses = self.get_yearly_expenses(user_id)

        return {
            'total_spent': total_spent,
            'category_totals': dict(sorted_categories),
            'top_expense_category': sorted_categories[0] if sorted_categories else None,
            'budget_status': budget_status,
            'monthly_expenses': monthly_expenses,
            'yearly_expenses': yearly_expenses
        }

    def get_user_expenses_csv(self, user_id):
        expenses = self.get_user_expenses(user_id)
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Date', 'Category', 'Amount', 'Description'])
        for expense in expenses:
            writer.writerow([expense.date, expense.category, expense.amount, expense.description])
        
        return output.getvalue()

    def __del__(self):
        self.conn.close()
