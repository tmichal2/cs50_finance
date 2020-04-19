import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

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

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Set current cash
    current_cash = db.execute(
        "SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]['cash']
    cash = usd(float(current_cash))

    # Access stocks and quantity user owns
    user_assets = db.execute(
        "SELECT stock_symbol, SUM(quantity) FROM transactions WHERE user_id=:id GROUP BY stock_symbol", id=session["user_id"])

    grand_total = 0
    for row in user_assets:
        stock = lookup(row['stock_symbol'])
        row['price'] = usd(stock['price'])
        row['stock_symbol'] = stock['symbol']
        row['stock_name'] = stock['name']
        row['total'] = usd(stock['price'] * row['SUM(quantity)'])
        grand_total += stock['price'] * row['SUM(quantity)']

    total_assets = usd(float(current_cash) + float(grand_total))
    print(lookup('aapl'))
    print(user_assets)

    return render_template("index.html",
                           user_assets=user_assets,
                           cash=cash,
                           total_assets=total_assets)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        # Error check
        if not request.form.get("buy_stock"):
            return redirect("/buy")
        stock_dict = lookup(request.form.get("buy_stock"))
        if stock_dict == None:
            return apology("Please enter a valid stock symbol")

        # Set variables from forms and database
        quantity = int(request.form.get("quantity"))
        symbol = stock_dict['symbol']
        price = float(stock_dict['price'])
        cost = price * quantity
        current_cash = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]['cash']

        # Print to terminal to check
        print(f"price: ", price)
        print(f"quantity: ", quantity)
        print(f"current cash: ", current_cash)

        # Ensure user can afford purchase
        if current_cash - cost < 0:
            return apology("Not enough cash", 403)

        # Insert purchase into transactions
        db.execute("INSERT INTO transactions(user_id, transaction_type, stock_symbol, quantity, price) VALUES (:user_id, :transaction_type, :stock_symbol, :quantity, :price)",
                   user_id=session["user_id"],
                   transaction_type="BUY",
                   stock_symbol=symbol,
                   quantity=quantity,
                   price=price)

        # Update user's new cash holdings
        db.execute("UPDATE users SET cash=:new_cash WHERE id=:id",
                   new_cash=(current_cash-cost),
                   id=session["user_id"])

        # Return user to index
        return redirect("/")

    # If GET request
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute(
        "SELECT timestamp, transaction_type, stock_symbol, quantity, price FROM transactions WHERE user_id=:id", id=session["user_id"])

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if not request.form.get("stock"):
            return redirect("/quote")
        stock_dict = lookup(request.form.get("stock"))
        if stock_dict == None:
            return apology("Please enter a valid stock symbol")
        print(lookup(request.form.get("stock")))
        return render_template("quoted.html", stock=stock_dict)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password entry
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password confirmation entry
        if not request.form.get("confirm_password"):
            return apology("must confirm password", 403)

        # Ensure matching passwords
        if request.form.get("password") != request.form.get("confirm_password"):
            return apology("passwords must match", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        if len(rows) != 0:
            return apology("username is already taken", 403)

        # Insert username and hashed pw into db
        new_hash = generate_password_hash(request.form.get("password"))
        print(new_hash)
        new_user = db.execute("INSERT INTO users(username, hash) VALUES (:username, :hash);",
                              username=request.form.get("username"),
                              hash=new_hash)

        session["user_id"] = new_user

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Must pick a stock
        if not request.form.get("symbol"):
            return apology("Must choose stock to sell")

        # Must sell more than quantity 0
        if int(request.form.get("quantity")) <= 0:
            return apology("Must sell more than zero shares")

        # Retrieve sale parameters
        stock_symbol = request.form.get("symbol")
        quantity = int(request.form.get("quantity"))

        # Retrieve stock info from API
        stock = lookup(stock_symbol)

        sale_price = stock['price'] * quantity

        # Check that user has sufficient stock to sell
        user_stock = db.execute(
            "SELECT SUM(quantity) as quantity FROM transactions WHERE user_id=:id AND stock_symbol=:symbol GROUP BY stock_symbol", id=session["user_id"], symbol=stock_symbol)

        if int(user_stock[0]['quantity']) < quantity:
            return apology("Not enough shares to sell", 403)

        # Insert SELL transaction
        db.execute("INSERT INTO transactions(user_id, transaction_type, stock_symbol, quantity, price) VALUES (:user_id, :transaction_type, :stock_symbol, :quantity, :price)",
                   user_id=session["user_id"],
                   transaction_type="SELL",
                   stock_symbol=stock_symbol,
                   quantity=(quantity * -1),
                   price=stock['price'])

        # Set current cash
        current_cash = db.execute(
            "SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]['cash']

        # Update cash holdings
        db.execute("UPDATE users SET cash=:new_cash WHERE id=:id",
                   new_cash=(current_cash + sale_price),
                   id=session["user_id"])

        return redirect("/")

    # If GET request.method
    else:
        # Query user-owned stocks
        stocks_owned = db.execute(
            "SELECT DISTINCT stock_symbol FROM transactions WHERE user_id=:id AND quantity > 0", id=session["user_id"])

        # Return template with user owned stocks
        return render_template("sell.html", stocks_owned=stocks_owned)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
