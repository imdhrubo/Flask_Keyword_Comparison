from flask import Flask, request, render_template, redirect, url_for, session, send_file
from flask_session import Session
import pandas as pd
import secrets
import io
import traceback

app = Flask(__name__)

# Configure the session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = secrets.token_hex(16)
Session(app)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        try:
            df = pd.read_excel(file)
            session['df'] = df.to_dict()  # Save DataFrame to session
            activity_ids = df['Activity ID'].tolist()
            # Exclude "Averages" from activity IDs
            activity_ids = [id for id in activity_ids if id != "Averages"]
            session['activity_ids'] = activity_ids
            return render_template('index.html', activity_ids=activity_ids)
        except Exception as e:
            print(f"Error processing file: {e}")
            print(traceback.format_exc())  # Detailed error logging
            return "There was an error processing the file. Please ensure it is a valid Excel file with the correct format."
    
    # If session data exists, render the dropdown with activity IDs
    if 'activity_ids' in session:
        activity_ids = session['activity_ids']
        return render_template('index.html', activity_ids=activity_ids)

    # Default behavior: render file upload form
    return render_template('index.html', activity_ids=None)

@app.route('/comparison', methods=['POST'])
def comparison():
    try:
        activity_id = request.form['activity_id']
        df = pd.DataFrame(session['df'])
        row_num = df[df['Activity ID'] == activity_id].index[0]

        manual_keywords = df.loc[row_num, 'Lemmatized Manual Keywords'].split(',')
        gpt_keywords = df.loc[row_num, 'Lemmatized Keywords by GPT'].split(',')
        gemini_keywords = df.loc[row_num, 'Lemmatized Keywords by Gemini'].split(',')

        activity_id = df.loc[row_num, 'Activity ID']
        activity_name = df.loc[row_num, 'Activity Name']

        # Strip and replace empty strings with "-"
        manual_keywords = [kw.strip() if kw.strip() else '-' for kw in manual_keywords]
        gpt_keywords = [kw.strip() if kw.strip() else '-' for kw in gpt_keywords]
        gemini_keywords = [kw.strip() if kw.strip() else '-' for kw in gemini_keywords]

        # Find common keywords
        common_all = set(manual_keywords).intersection(set(gpt_keywords)).intersection(set(gemini_keywords))
        common_manual_gpt = set(manual_keywords).intersection(set(gpt_keywords)) - common_all
        common_manual_gemini = set(manual_keywords).intersection(set(gemini_keywords)) - common_all
        common_gpt_gemini = set(gpt_keywords).intersection(set(gemini_keywords)) - common_all

        # Align keywords
        aligned_data = {
            'Manual': [],
            'GPT': [],
            'Gemini': []
        }

        # Process common keywords across all three
        for kw in common_all:
            aligned_data['Manual'].append(kw)
            aligned_data['GPT'].append(kw)
            aligned_data['Gemini'].append(kw)

        # Process common keywords between Manual and GPT
        for kw in common_manual_gpt:
            aligned_data['Manual'].append(kw)
            aligned_data['GPT'].append(kw)
            aligned_data['Gemini'].append('-')

        # Process common keywords between Manual and Gemini
        for kw in common_manual_gemini:
            aligned_data['Manual'].append(kw)
            aligned_data['GPT'].append('-')
            aligned_data['Gemini'].append(kw)

        # Process common keywords between GPT and Gemini
        for kw in common_gpt_gemini:
            aligned_data['Manual'].append('-')
            aligned_data['GPT'].append(kw)
            aligned_data['Gemini'].append(kw)

        # Process unique keywords
        unique_manual = set(manual_keywords) - common_all - common_manual_gpt - common_manual_gemini
        unique_gpt = set(gpt_keywords) - common_all - common_manual_gpt - common_gpt_gemini
        unique_gemini = set(gemini_keywords) - common_all - common_manual_gemini - common_gpt_gemini

        for kw in unique_manual:
            aligned_data['Manual'].append(kw)
            aligned_data['GPT'].append('-')
            aligned_data['Gemini'].append('-')

        for kw in unique_gpt:
            aligned_data['Manual'].append('-')
            aligned_data['GPT'].append(kw)
            aligned_data['Gemini'].append('-')

        for kw in unique_gemini:
            aligned_data['Manual'].append('-')
            aligned_data['GPT'].append('-')
            aligned_data['Gemini'].append(kw)

        # Normalize the length of lists
        max_length = max(len(aligned_data['Manual']), len(aligned_data['GPT']), len(aligned_data['Gemini']))
        for key in aligned_data:
            aligned_data[key].extend(['-'] * (max_length - len(aligned_data[key])))

        session['comparison_data'] = aligned_data
        session['activity_id'] = activity_id
        session['activity_name'] = activity_name

        print(f"Aligned comparison data: {aligned_data}")  # Debugging statement
        return render_template('comparison.html', data=aligned_data, activity_id=activity_id, activity_name=activity_name)
    except Exception as e:
        print(f"Error during comparison: {e}")
        print(traceback.format_exc())  # Detailed error logging
        return "There was an error during comparison. Please try again."

@app.route('/export')
def export():
    try:
        data = session.get('comparison_data')
        activity_id = session.get('activity_id')
        activity_name = session.get('activity_name')

        if not data:
            return redirect(url_for('index'))

        df_export = pd.DataFrame(data)
        output = io.StringIO()
        df_export.to_csv(output, index=False)
        output.seek(0)

        return send_file(
            io.BytesIO(output.getvalue().encode()), 
            mimetype='text/csv',
            as_attachment=True, 
            download_name=f'comparison_{activity_id}.csv'
        )
    except Exception as e:
        print(f"Error during export: {e}")
        print(traceback.format_exc())  # Detailed error logging
        return "There was an error during export. Please try again."

if __name__ == '__main__':
    app.run(debug=True, port=5002)
