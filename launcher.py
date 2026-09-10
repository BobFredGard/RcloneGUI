import sys
import os
import traceback

log_file = open(os.path.join(os.path.dirname(__file__), 'startup.log'), 'w')
sys.stdout = log_file
sys.stderr = log_file

try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    log_file.write("Starting...\n")
    log_file.flush()

    from app import app
    log_file.write("App imported\n")
    log_file.flush()

    from waitress import serve
    log_file.write("Starting waitress...\n")
    log_file.flush()

    serve(app, host='0.0.0.0', port=5000)
except Exception as e:
    log_file.write(f"Error: {e}\n")
    log_file.write(traceback.format_exc())
finally:
    log_file.close()
