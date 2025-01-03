from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_socketio import SocketIO
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from expense_manager import ExpenseManager, User
from init_db import init_db
import sqlite3
import io
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key in production
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Initialize the database if it doesn't exist
if not os.path.exists('expenses.db'):
    init_db()

expense_manager = ExpenseManager()

@login_manager.user_loader
def load_user(user_id):
    return expense_manager.get_user_by_id(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if expense_manager.get_user_by_username(username):
            flash('Username already exists', 'error')
        elif expense_manager.get_user_by_email(email):
            flash('Email already exists', 'error')
        else:
            user_id = expense_manager.add_user(username, email, password)
            if user_id:
                user = expense_manager.get_user_by_id(user_id)
                login_user(user)
                flash('Registration successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = expense_manager.get_user_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    expenses = expense_manager.get_user_expenses(current_user.id)
    return render_template('index.html', expenses=expenses)

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    category = request.form['category']
    amount = float(request.form['amount'])
    description = request.form['description']
    new_expense = expense_manager.add_expense(current_user.id, category, amount, description)
    socketio.emit('new_expense', new_expense.to_dict(), room=current_user.get_id())
    return jsonify(success=True)

@app.route('/analyze')
@login_required
def analyze():
    analysis = expense_manager.analyze_user_expenses(current_user.id)
    return render_template('analysis.html', analysis=analysis)

@app.route('/set_budget', methods=['GET', 'POST'])
@login_required
def set_budget():
    if request.method == 'POST':
        category = request.form['category']
        amount = float(request.form['amount'])
        expense_manager.set_budget(current_user.id, category, amount)
        flash('Budget set successfully')
        return redirect(url_for('index'))
    return render_template('set_budget.html')

@app.route('/export_csv')
@login_required
def export_csv():
    csv_data = expense_manager.get_user_expenses_csv(current_user.id)
    return send_file(
        io.BytesIO(csv_data.encode()),
        mimetype='text/csv',
        as_attachment=True,
        attachment_filename='expenses.csv'
    )

@socketio.on('connect')
def handle_connect():
    print('Client connected')

if __name__ == '__main__':
    socketio.run(app, debug=True)

