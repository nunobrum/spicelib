import tkinter as tk

# Create the Tkinter window
root = tk.Tk()
root.geometry("400x300")  # Set window size
root.title("www.plus2net.com Clipboard Example")  # Window title

# Textbox widget for input/output
text_box = tk.Text(
    root, 
    width=40, 
    height=10, 
    bg="#ffffe0",  # Light yellow background
    font=("Arial", 12)  # Font style and size
)  
text_box.grid( row=0, column=0,columnspan=2, 
    padx=10, 
    pady=10
)  # Position the Text widget

# Function to copy content to the clipboard
def copy_to_clipboard():
    root.clipboard_clear()  # Clear clipboard content
    root.clipboard_append(
        text_box.get("1.0", tk.END).strip()
    )  # Copy Text widget content
    root.update()  # Update clipboard content
    print(
        "Copied to clipboard:", 
        text_box.get("1.0", tk.END).strip()
    )  # Log copied content

# Function to paste content from the clipboard
def paste_from_clipboard():
    try:
        content = root.clipboard_get()  # Get clipboard content
        text_box.delete("1.0", tk.END)  # Clear existing text
        text_box.insert("1.0", content)  # Insert clipboard content
        print("Pasted from clipboard:", content)  # Log pasted content
    except tk.TclError:  # Handle empty clipboard error
        print("Clipboard is empty!")

# Button to copy content to clipboard
copy_btn = tk.Button(
    root, 
    text="Copy", 
    command=copy_to_clipboard, 
    bg="#4caf50",  # Green background
    fg="white",  # White text
    font=("Arial", 12), 
    width=12
)
copy_btn.grid(
    row=1, 
    column=0, 
    padx=5, 
    pady=10
)  # Position Copy button

# Button to paste content from clipboard
paste_btn = tk.Button(
    root, 
    text="Paste", 
    command=paste_from_clipboard, 
    bg="#2196f3",  # Blue background
    fg="white",  # White text
    font=("Arial", 12), 
    width=12
)
paste_btn.grid(
    row=1, 
    column=1, 
    padx=5, 
    pady=10
)  # Position Paste button

# Run the application
root.mainloop()  # Start the Tkinter event loop
