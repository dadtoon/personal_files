import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def lookup(symbol):
	try:
		api_key = os.environ.get("API_KEY")
		response = requests.get(f"https://cloud-sse.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token=pk_eb9d2b0247de438f830b208b1f3805a9")
		response.raise_for_status()
	except requests.RequestException:
		return None

	try:
		quote = response.json()
		return {
			"name": quote["companyName"],
			"price": float(quote["latestPrice"]),
			"symbol": quote["symbol"]
		}
	except (KeyError, TypeError, ValueError):
		return None

def usd(value):
	return f"${value:. .2f}"

