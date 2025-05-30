from flask import Flask, jsonify, render_template
from yahoo_fin import stock_info
from datetime import datetime
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from forex_python.converter import CurrencyRates
import os
import requests
import time
import json

load_dotenv()
app = Flask(__name__)
# Allow all origins for now, but you should restrict this in production
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

@app.route('/')
def index():
    return render_template('testsocket.html')

def get_currency_data_multiple_sources(from_currency, to_currency):
    """Try multiple APIs in order of preference"""
    
    # Method 1: Free ExchangeRate API
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if to_currency in data['rates']:
            rate = data['rates'][to_currency]
            return {
                "currency": f"{from_currency} to {to_currency}",
                "current_rate": round(rate, 4),
                "today": datetime.now().date().isoformat(),
                "source": "exchangerate-api.com",
                "status": "success"
            }
    except Exception as e:
        print(f"ExchangeRate API failed: {e}")
    
    # Method 2: Fixer.io (backup)
    try:
        url = f"https://api.fixer.io/latest?base={from_currency}&symbols={to_currency}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'rates' in data and to_currency in data['rates']:
            rate = data['rates'][to_currency]
            return {
                "currency": f"{from_currency} to {to_currency}",
                "current_rate": round(rate, 4),
                "today": datetime.now().date().isoformat(),
                "source": "fixer.io",
                "status": "success"
            }
    except Exception as e:
        print(f"Fixer.io API failed: {e}")
    
    # Method 3: CurrencyAPI (another backup)
    try:
        url = f"https://api.currencyapi.com/v3/latest?apikey=YOUR_API_KEY&base_currency={from_currency}&currencies={to_currency}"
        # Note: You'll need to get a free API key from currencyapi.com
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data and to_currency in data['data']:
            rate = data['data'][to_currency]['value']
            return {
                "currency": f"{from_currency} to {to_currency}",
                "current_rate": round(rate, 4),
                "today": datetime.now().date().isoformat(),
                "source": "currencyapi.com",
                "status": "success"
            }
    except Exception as e:
        print(f"CurrencyAPI failed: {e}")
    
    # Method 4: Forex-python (last resort)
    try:
        c = CurrencyRates()
        rate = c.get_rate(from_currency, to_currency)
        return {
            "currency": f"{from_currency} to {to_currency}",
            "current_rate": round(rate, 4),
            "today": datetime.now().date().isoformat(),
            "source": "forex-python",
            "status": "success"
        }
    except Exception as e:
        print(f"Forex-python failed: {e}")
    
    # If all methods fail
    return {
        "currency": f"{from_currency} to {to_currency}",
        "error": "All currency APIs failed",
        "status": "error",
        "today": datetime.now().date().isoformat()
    }

def get_currency_data_yahoo(ticker, currency_name):
    """Improved Yahoo Finance data fetching with better error handling"""
    try:
        # Add delay to avoid rate limiting
        time.sleep(0.5)
        
        # Try to get live price
        rate = stock_info.get_live_price(ticker)
        
        today = datetime.now().date()
        
        # Try to get historical data with error handling
        try:
            historical_data = stock_info.get_data(ticker, start_date=today, end_date=today)
            if not historical_data.empty:
                today_high = float(historical_data['high'].values[0])
                today_low = float(historical_data['low'].values[0])
            else:
                today_high = None
                today_low = None
        except Exception as hist_error:
            print(f"Historical data error for {ticker}: {hist_error}")
            today_high = None
            today_low = None
        
        return {
            "currency": currency_name,
            "current_rate": round(float(rate), 4),
            "today_high": round(today_high, 4) if today_high else None,
            "today_low": round(today_low, 4) if today_low else None,
            "today": today.isoformat(),
            "source": "yahoo_finance",
            "status": "success"
        }
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return {
            "currency": currency_name,
            "error": str(e),
            "status": "error",
            "today": datetime.now().date().isoformat()
        }

@app.route('/api/convert/aed-to-inr', methods=['GET', 'POST'])
def aed_to_inr():
    response = get_currency_data_multiple_sources("AED", "INR")
    socketio.emit('currency_update', response)
    
    if response.get("status") == "error":
        return jsonify(response), 500
    return jsonify(response)

@app.route('/api/convert/usd-to-inr')
def usd_to_inr():
    response = get_currency_data_multiple_sources("USD", "INR")
    socketio.emit('currency_update', response)
    
    if response.get("status") == "error":
        return jsonify(response), 500
    return jsonify(response)

@app.route('/api/convert/aed-to-myr', methods=['GET', 'POST'])
def aed_to_myr():
    response = get_currency_data_multiple_sources("AED", "MYR")
    socketio.emit('currency_update', response)
    
    if response.get("status") == "error":
        return jsonify(response), 500
    return jsonify(response)

@app.route('/api/convert/aed-to-usd', methods=['GET', 'POST'])
def aed_to_usd():
    response = get_currency_data_multiple_sources("AED", "USD")
    socketio.emit('currency_update', response)
    
    if response.get("status") == "error":
        return jsonify(response), 500
    return jsonify(response)

@app.route('/api/rates/all-aed')
def get_all_aed_rates():
    """Get all AED conversion rates in one call"""
    target_currencies = ['INR', 'MYR', 'USD']
    
    results = {}
    
    for currency in target_currencies:
        result = get_currency_data_multiple_sources("AED", currency)
        results[f"AED_TO_{currency}"] = result
    
    return jsonify({
        "base_currency": "AED",
        "target_currencies": target_currencies,
        "rates": results,
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    })
def test_connection():
    """Test endpoint to check if APIs are working"""
    results = {}
    
    # Test different APIs
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
        results['exchangerate-api'] = 'working' if response.status_code == 200 else 'failed'
    except:
        results['exchangerate-api'] = 'failed'
    
    try:
        c = CurrencyRates()
        rate = c.get_rate('USD', 'INR')
        results['forex-python'] = 'working'
    except:
        results['forex-python'] = 'failed'
    
    try:
        rate = stock_info.get_live_price('AAPL')
        results['yahoo-finance'] = 'working'
    except:
        results['yahoo-finance'] = 'failed'
    
    return jsonify(results)

@socketio.on('connect')
def handle_connect():
    print("Client connected")
    socketio.sleep(0.1)
    emit('message', {'data': 'Connected to the server'})

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

@socketio.on('start_updates')
def start_currency_updates():
    """Emit currency updates to clients every 30 seconds."""
    while True:
        try:
            # Get all AED conversions
            aed_to_inr_response = get_currency_data_multiple_sources("AED", "INR")
            aed_to_myr_response = get_currency_data_multiple_sources("AED", "MYR")
            aed_to_usd_response = get_currency_data_multiple_sources("AED", "USD")
            usd_to_inr_response = get_currency_data_multiple_sources("USD", "INR")
            
            # Emit individual updates
            socketio.emit('currency_update', {'type': 'AED_TO_INR', 'data': aed_to_inr_response})
            socketio.emit('currency_update', {'type': 'AED_TO_MYR', 'data': aed_to_myr_response})
            socketio.emit('currency_update', {'type': 'AED_TO_USD', 'data': aed_to_usd_response})
            socketio.emit('currency_update', {'type': 'USD_TO_INR', 'data': usd_to_inr_response})
            
            # Emit bulk update
            socketio.emit('bulk_currency_update', {
                'AED_TO_INR': aed_to_inr_response,
                'AED_TO_MYR': aed_to_myr_response,
                'AED_TO_USD': aed_to_usd_response,
                'USD_TO_INR': usd_to_inr_response,
                'timestamp': datetime.now().isoformat()
            })
            
            print(f"Sent updates - AED-INR: {aed_to_inr_response.get('current_rate', 'Error')}, "
                  f"AED-MYR: {aed_to_myr_response.get('current_rate', 'Error')}, "
                  f"AED-USD: {aed_to_usd_response.get('current_rate', 'Error')}, "
                  f"USD-INR: {usd_to_inr_response.get('current_rate', 'Error')}")
            
        except Exception as e:
            print(f"Error in currency updates: {e}")
            socketio.emit('currency_update', {
                'error': f'Update failed: {str(e)}',
                'status': 'error'
            })
        
        socketio.sleep(30)  # Wait 30 seconds

if __name__ == '__main__':
    # Start background updates
    socketio.start_background_task(start_currency_updates)
    
    # Get port and debug mode from environment variables
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)

