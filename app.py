from flask import Flask
app= Flask(__name__)
@app.route('/')
def home():
    return "Hostel Help Desk"
if  __name__ == "__main__":
    app.run(debug=True)
