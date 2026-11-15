# desktop_app.py
<<<<<<< HEAD
import webview
import threading
import time
from resume_screener import create_gradio_interface
=======
import threading
import time

import webview

from app import create_gradio_interface

>>>>>>> branch6

def run_gradio():
    """Launch the Gradio interface"""
    interface = create_gradio_interface()
    interface.launch(server_name="127.0.0.1", server_port=7860, share=False)

<<<<<<< HEAD
=======

>>>>>>> branch6
def main():
    # Start Gradio in a background thread
    gradio_thread = threading.Thread(target=run_gradio, daemon=True)
    gradio_thread.start()
<<<<<<< HEAD
    
    # Wait for Gradio to start up
    time.sleep(3)  # Give it a few seconds to initialize
    
=======

    # Wait for Gradio to start up
    time.sleep(3)  # Give it a few seconds to initialize

>>>>>>> branch6
    # Create a native window pointing to the Gradio app
    webview.create_window(
        "Resume Screening System",
        "http://127.0.0.1:7860",
        width=1200,
        height=800,
        resizable=True,
        fullscreen=False,
        min_size=(800, 600)
    )
<<<<<<< HEAD
    
    # Start the desktop application
    webview.start()

if __name__ == "__main__":
    main()
=======

    # Start the desktop application
    webview.start()


if __name__ == "__main__":
    main()
>>>>>>> branch6
