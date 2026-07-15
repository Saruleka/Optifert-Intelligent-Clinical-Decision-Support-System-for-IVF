# 🧬 OptiFert – AI-Powered IVF Trigger Decision Support System

OptiFert is an AI-powered clinical decision support system designed to assist fertility specialists in determining the optimal ovulation trigger timing during **In Vitro Fertilization (IVF)** treatment. The platform combines machine learning, explainable AI, and a secure web application to provide personalized treatment recommendations, assess OHSS risk, estimate mature oocyte yield, and streamline patient management.

> **Note:** This project is developed for educational and research purposes and is not intended for direct clinical use.

---

## ✨ Features

* AI-based ovulation trigger timing prediction
* OHSS (Ovarian Hyperstimulation Syndrome) risk assessment
* Mature (MII) oocyte yield estimation
* Explainable AI recommendations with clinical reasoning
* Role-based authentication for doctors and patients
* Appointment booking and management
* IVF cycle tracking and historical review
* Automated high-risk patient alerts
* Treatment simulation ("What-If" analysis)

---

## 🛠️ Tech Stack

| Category         | Technologies          |
| ---------------- | --------------------- |
| Backend          | Python, Flask         |
| Machine Learning | Scikit-learn          |
| Database         | SQLite                |
| Data Processing  | Pandas, NumPy         |
| Frontend         | HTML, CSS, JavaScript |

---

## 📂 Project Structure

```text
OptiFert/
├── app.py                     # Flask application
├── db.py                      # Database operations
├── generate_dataset.py        # Synthetic dataset generation
├── ml_service.py              # Machine learning inference engine
├── ivf_trigger_models_v2.pkl  # Trained ML models
├── ivf_synthetic_dataset.csv  # Synthetic training dataset
├── static/                    # CSS, JavaScript, images
├── templates/                 # HTML templates
├── requirements.txt
└── README.md
```

---

## ⚙️ System Workflow

```text
Synthetic Dataset Generation
            ↓
Machine Learning Model Training
            ↓
Trained Prediction Models
            ↓
Flask Web Application
            ↓
Doctor Inputs Clinical Data
            ↓
Real-Time Prediction Engine
            ↓
Trigger Timing • OHSS Risk • MII Estimation
            ↓
Clinical Explanations & Safety Rules
            ↓
Cycle History & Alerts Stored in Database
```

---

## 🧠 Machine Learning Pipeline

The prediction engine performs three primary tasks:

* **Trigger Timing Prediction** – Recommends the optimal ovulation trigger timing using a Random Forest classifier.
* **OHSS Risk Prediction** – Estimates the patient's risk of ovarian hyperstimulation syndrome.
* **MII Egg Estimation** – Predicts the expected number of mature oocytes using a Gradient Boosting regressor.

To improve clinical reliability, model predictions are validated using rule-based safety checks before recommendations are presented.

---

## 🗄️ Database

The application uses **SQLite** with relational tables to manage:

* User authentication
* Doctor and patient profiles
* Appointments
* IVF cycle history
* Automated clinical alerts

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/OptiFert.git
cd OptiFert
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
python app.py
```

The application will start on:

```text
http://127.0.0.1:5000
```

---

## 📌 Future Improvements

* Deep learning-based ultrasound image analysis
* Electronic Health Record (EHR) integration
* Cloud deployment
* REST API support
* Mobile application
* Multi-center clinical validation

---

## 📄 License

This project is intended for academic and research purposes. It should not be used as a substitute for professional medical advice or clinical decision-making.

---

## 👩‍💻 Authors

Developed as part of an academic software engineering and machine learning project focused on applying Explainable AI to IVF clinical decision support.

