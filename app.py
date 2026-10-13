from flask import Flask, render_template

app = Flask(__name__)

REQUEST_TYPES = ["Cleaning", "Plumbing", "Electrical", "Wi-Fi", "Furniture", "Other"]


@app.route("/")
def report():
    return render_template("report.html", types=REQUEST_TYPES)


if __name__ == "__main__":
    app.run(debug=True)
