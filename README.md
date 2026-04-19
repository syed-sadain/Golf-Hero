⛳ # GolfHero — Subscription Golf Platform

A full-stack Flask + PostgreSQL application that combines golf scoring, monthly draw systems, and charity contributions into one platform.

#🚀 Tech Stack
Backend: Python 3.12 + Flask 3
Database: PostgreSQL
Frontend: HTML, CSS (Glassmorphism UI), JavaScript
Authentication: Session-based (Flask)
Payments: Stripe (via environment variables)
Deployment: Render / Heroku
#✨ Core Features
✅ Subscription system (Monthly / Yearly)
✅ Score tracking (Stableford 1–45)
✅ Rolling last 5 scores logic
✅ Monthly draw system (Random + Algorithm)
✅ Prize pool calculation + jackpot rollover
✅ Charity contribution system (min 10%)
✅ Admin dashboard (full control panel)
✅ Winner verification + proof upload
✅ Modern UI (Glassmorphism + gradients)
# 📁 Project Structure
golfhero/
├── app.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── .env.example
├── .gitignore
├── static/
│   ├── css/
│   └── js/
└── templates/
    ├── base.html
    ├── index.html
    ├── signup.html
    ├── login.html
    ├── dashboard.html
    ├── charities.html
    ├── how_it_works.html
    └── admin/
⚙️ Environment Variables

Create a .env file (or set in Render/Heroku):

SECRET_KEY=your_secret_key

DATABASE_URL=your_database_url

STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...

MONTHLY_PRICE_ID=price_...
YEARLY_PRICE_ID=price_...
🖥️ Local Development Setup
# Clone repo
git clone https://github.com/syed-sadain/Golf-Hero.git
cd Golf-Hero

# Create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Setup PostgreSQL database
createdb golfhero

# Run app
python app.py

Open:

http://127.0.0.1:5000
🌐 Render Deployment (Recommended)
1. Push to GitHub ✅ (already done)
2. Create Web Service on Render
Go to Render Dashboard
Click New → Web Service
Connect your GitHub repo
3. Add Environment Variables

In Render → Environment:

DATABASE_URL=postgresql://golfhero_user:...@.../golfhero
SECRET_KEY=your_secret_key
FLASK_DEBUG=0
4. Build & Start Command

Build Command:

pip install -r requirements.txt

Start Command:

python app.py
🔑 Default Admin Login
Role	Email	Password
Admin	admin@golfhero.com
	Admin@123

⚠️ Important: Change password after first login.

🎯 System Design Highlights
Draw Engine
Random mode → fair selection
Algorithm mode → weighted by user scores
Prize Pool Logic
40% → 5-match
35% → 4-match
25% → 3-match
10% → charity
Security
Password hashing (Werkzeug)
Session-based authentication
Admin role protection
🛠️ Troubleshooting
❌ Database Connection Error
psql "your_database_url"
❌ Render not connecting
Ensure DATABASE_URL is correct
Use External URL (not internal)
❌ App crashes
# Render logs
Check logs in dashboard
📌 Future Improvements
Docker support
JWT authentication
Payment webhook verification
Email notifications
Advanced analytics dashboard
#👨‍💻 Author

Syed Sadain

Python | Flask | PostgreSQL | Backend Developer
📄 License

This project is for educational & internship purposes.
