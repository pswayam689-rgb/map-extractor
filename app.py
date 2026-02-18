import os
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for # Adjusted to include redirect and url_for
from scraper import scrape_google_maps

app = Flask(__name__)

# --- GLOBAL STOP STATE ---
stop_requested = False

def get_all_leads_safely():
    """Helper function to read the CSV without crashing the app."""
    filename = "all_leads.csv"
    try:
        if os.path.exists(filename):
            # 'on_bad_lines' skips rows that don't match the column count
            df = pd.read_csv(filename, on_bad_lines='warn', engine='python')
            # Convert to dictionary and reverse (newest at top)
            return df.iloc[::-1].to_dict(orient='records')
        return []
    except Exception as e:
        print(f"⚠️ Error reading CSV: {e}")
        return []

@app.route('/')
def index():
    all_data = get_all_leads_safely()
    return render_template('index.html', results=all_data)

@app.route('/stop', methods=['POST'])
def stop():
    global stop_requested
    stop_requested = True
    print("🛑 Stop request received...")
    return "Stopping...", 200

@app.route('/search', methods=['POST'])
def search():
    global stop_requested
    stop_requested = False  # Reset signal for a new search
    
    keyword = request.form.get('keyword')
    
    # 1. Run the scraper and pass the stop-check function
    # The scraper will call lambda: stop_requested to see if it should quit
    scrape_google_maps(keyword, max_results=20, check_stop=lambda: stop_requested)
    
    # 2. Read the master file (includes new data and old data)
    all_data = get_all_leads_safely()

    # 3. Stay on the same page and show the keyword in the search box
    return render_template('index.html', results=all_data, keyword=keyword)

@app.route('/download')
def download_file():
    # Use the same filename your scraper uses
    filename = "all_leads.csv" 
    
    # Get the absolute path to make sure Flask finds it
    file_path = os.path.join(os.getcwd(), filename)
    
    if os.path.exists(file_path):
        try:
            return send_file(
                file_path,
                as_attachment=True,
                download_name="google_maps_leads.csv", # What the user sees
                mimetype='text/csv'
            )
        except Exception as e:
            return f"Error during download: {str(e)}", 500
    else:
        # If the file isn't there, show a better message than just "Not Found"
        return "<h3>❌ No data file found yet.</h3><p>Please run a search first to generate the CSV file.</p><a href='/'>Back to Home</a>", 404

# --- ADJUSTED: Fixed indentation so this is a standalone route ---
@app.route('/clear', methods=['POST'])
def clear_data():
    filename = "all_leads.csv"
    if os.path.exists(filename):
        os.remove(filename)
        print("🗑️ Database cleared successfully.")
    return redirect(url_for('index')) 


# 2. Keep the run command on its own line at the bottom
if __name__ == "__main__":
    app.run(debug=True, threaded=True)