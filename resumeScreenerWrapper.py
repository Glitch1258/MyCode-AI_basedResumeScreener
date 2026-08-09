# desktop_app.py
import webview
import threading
import time
from resume_screener import create_gradio_interface

def run_gradio():
    """Launch the Gradio interface"""
    interface = create_gradio_interface()
    interface.launch(server_name="127.0.0.1", server_port=7860, share=False)

def main():
    # Start Gradio in a background thread
    gradio_thread = threading.Thread(target=run_gradio, daemon=True)
    gradio_thread.start()
    
    # Wait for Gradio to start up
    time.sleep(3)  # Give it a few seconds to initialize
    
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
    
    # Start the desktop application
    webview.start()

if __name__ == "__main__":
    main()