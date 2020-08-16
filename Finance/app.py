import os

import sqlite3
from flask import Flask, flash, jsonify, render_template, redirect, request, session
from flask_session import Session
import time
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, lookup, usd

app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
	response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
	response.headers["Expires"] = 0
	response.headers["Pragma"] = "no-cache"
	return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Make sure API key is set
#if not os.environ.get("API_KEY"):
#    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
	"""  Show portfolio of stocks"""
	conn = sqlite3.connect("finance.db")
	cursor = conn.cursor()
	stocks = cursor.execute("""SELECT transactionID, companyName, companySymbol, transactedPrice, SUM(numberofShare), 
							transactedDate, userID FROM Transactions WHERE userID = ? GROUP BY companyName;""", (session['user_id'], )).fetchall()

	stocks = [list(stock) for stock in stocks] 
	for stock in stocks:
		stock = stock.append(lookup(stock[2])['price'])
	
	for stock in stocks:	
		latestStock = int(stock[4]) * float(stock[7])
		stock = stock.append(round(latestStock, 2))

	stockHolder = []
	for stock in stocks:
		stockHolder.append(stock[8])

	cashBalance = cursor.execute("""SELECT cashBalance FROM Cash WHERE userID = ?;""", (session['user_id'], )).fetchone()[0]

	totalStock = round((sum(stockHolder) + cashBalance), 2)

	return render_template("index.html", stocks=stocks, cashBalance=cashBalance, totalStock=totalStock)

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
	""" Show quote of stock """
	if request.method == "POST":
		query = request.form.get("stock")
		stock = lookup(query)
		return render_template("quote.html", name=stock['name'] ,price=stock['price'])
	else:
		return render_template("quote.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
	""" Buy Stock """
	if request.method == "POST":
		conn = sqlite3.connect("finance.db")
		cursor = conn.cursor()

		query = request.form.get("stock")
		stock = lookup(query)
		
		user_id = session['user_id']
		name = stock["name"]
		price = int(stock["price"])
		symbol = stock["symbol"]
		share = int(request.form.get("share"))
		
		try:
			cursor.execute("""INSERT INTO Transactions (companyName, companySymbol, transactedPrice, numberofShare, userID) 
							VALUES (?,?,?,?,?);""", (name,symbol,price,share,user_id))
			conn.commit()
		except:
			return render_template("buy.html", warning="Transaction Error 2. Try again later.")
		try:
			time.sleep(5)
			buy = float(price)*int(share)
			cursor.execute("""UPDATE Cash SET cashBalance=cashBalance-? WHERE userID=? """, (buy, user_id))
			conn.commit()
		except:
			return render_template("buy.html", warning="Transaction Error 2. Try again later.")
		return redirect("/")
	else:
		return render_template("buy.html")

@app.route("/sell", methods=['GET', 'POST'])
@login_required
def sell():
	if request.method == "POST":
		conn = sqlite3.connect("finance.db")
		cursor = conn.cursor()
		
		query = request.form.get("stocks")
		stock = lookup(query)

		user_id = session['user_id']
		name = stock['name']
		symbol = stock['symbol']
		price = int(stock['price'])
		share = int(request.form.get("share"))

		current_shares = cursor.execute("""SELECT SUM(numberofShare) FROM Transactions WHERE userID=? AND companySymbol=?
						GROUP BY companySymbol;""", (user_id, symbol)).fetchone()[0]
		if current_shares < share:
			return render_template("sell.html", warning="Not enough share. Try again.")

		try:
			cursor.execute("""INSERT INTO Transactions (companyName, companySymbol, transactedPrice, numberofShare, userID)
										VALUES (?,?,?,?,?);""", (name,symbol,price,-share,user_id))
			conn.commit()
		except:
			return render_template("sell.html", warning="Transaction Error. Try again later.")
		try:
			time.sleep(5)
			sell = float(price)*int(share)
			cursor.execute("""UPDATE Cash SET cashBalance=cashBalance+? WHERE userID=? """, (sell,user_id))
			conn.commit()
		except:
			return render_template("sell.html", warning="Transaction Error. Try again later.")
		return redirect("/")
	else:
		conn = sqlite3.connect("finance.db")
		cursor = conn.cursor()
		stocks = cursor.execute("""SELECT companySymbol FROM Transactions WHERE userID=? GROUP BY companySymbol;""", (session['user_id'], )).fetchall()
		return render_template("sell.html", stocks=stocks)

@app.route("/history")
@login_required
def history():
	"""  Show history of transactions"""
	conn = sqlite3.connect("finance.db")
	cursor = conn.cursor()
	stocks = cursor.execute("""SELECT * FROM Transactions WHERE userID =? """, (session['user_id'], )).fetchall()

	return render_template("history.html", stocks=stocks)

@app.route("/login", methods=["GET", "POST"])
def login():
	""" Log in user """
	session.clear()

	if request.method == "POST":

		conn = sqlite3.connect("finance.db")
		cursor = conn.cursor()
		
		# Ensure username was submitted
		if not request.form.get("username"):
			return render_template("login.html", warning="Please insert username")
		# Ensure password was submitted
		elif not request.form.get("password"):
			return render_template("login.html", warning="Please insert password")
		#Ensure username exists and password is correct
		username = request.form.get("username")

		try:
			rows = cursor.execute("""SELECT * FROM Users WHERE userName=?; """, (username, ))
			data = rows.fetchone()

			if not check_password_hash(data[2], request.form.get("password")):
				return render_template("login.html", warning="Password is incorrect. Please try again")
		except:
			return render_template("login.html", warning="Invalid username. Please try again")

		# Remember which user has logged in	
		session["user_id"] = data[0]
		
		return redirect("/")	
	# User reached route via GET
	else:
		return render_template("login.html")

@app.route("/logout")
def logout():
	session.clear()
	return redirect("/")

@app.route("/signup", methods=["GET", "POST"])
def signup():
	""" Sign up user """

	session.clear()

	if request.method == "POST":
		conn = sqlite3.connect("finance.db")
		cursor = conn.cursor()

		# Ensure username was submitted
		if not request.form.get("username"):
			return render_template("signup.html", warning="Please insert username")
		# Ensure password was submitted
		elif not request.form.get("password"):
			return render_template("signup.html", warning="Please insert password")
		# Ensure password matches with confirm password
		elif not request.form.get("password") == request.form.get("confirm_password"):
			return render_template("signup.html", warning="Password did not match.")

		username = request.form.get("username")
		password = generate_password_hash(request.form.get("password"))

		try:
			cursor.execute("""INSERT INTO Users (userName, hash) VALUES (?,?);""", (username, password))
			conn.commit()
		except:
			return render_template("signup.html", warning="Username already exists. Try another.")

		time.sleep(3)
		money = 10000
		userID = cursor.execute("""SELECT userID FROM users WHERE userName = ?;""", (username,)).fetchone()[0]
		cursor.execute("""INSERT INTO Cash (userID, cashBalance) VALUES (?,?);""", (userID,money)) 
		conn.commit()
		return redirect("/login")
	else:
		return render_template("signup.html")

@app.route("/dummy")
def dummy():

	conn = sqlite3.connect("finance.db")
	#conn.row_factory = lambda cursor, row: row[0]
	cursor = conn.cursor()

	rows = cursor.execute("""SELECT numberofShare FROM Transactions;""").fetchall()

	total = []
	for row in rows:
		total.append(row[0])

	totalStock = sum(total)

	return render_template("dummy.html", rows=totalStock)

if __name__ == '__main__':
	app.run(debug=True)