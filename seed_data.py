from database import SessionLocal, engine
import models
from datetime import date, datetime
import random


def seed_database():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _seed_speakers_webinars(db)
    finally:
        db.close()


def _seed_speakers_webinars(db):
    if db.query(models.Speaker).count() > 0:
        return

    speakers_data = [
        {"name": "Anil Rego", "email": "anil.rego@finright.in", "bio": "Certified Financial Planner with 18+ years in personal finance and wealth management."},
        {"name": "Priya Sharma", "email": "priya.sharma@wealthwise.in", "bio": "Investment analyst and personal finance coach, ex-Goldman Sachs."},
        {"name": "Rajesh Kumar", "email": "rajesh.kumar@taxedge.in", "bio": "CA and Certified Tax Consultant specialising in tax planning for HNIs."},
        {"name": "Meera Nair", "email": "meera.nair@retireright.in", "bio": "Retirement planning specialist and founder of RetireRight Advisory."},
        {"name": "Vikram Patel", "email": "vikram.patel@equityiq.in", "bio": "Equity research veteran and portfolio manager with 20 years on Dalal Street."},
    ]

    speakers = []
    for sd in speakers_data:
        sp = models.Speaker(**sd)
        db.add(sp)
        speakers.append(sp)
    db.commit()
    for sp in speakers:
        db.refresh(sp)

    webinars_raw = [
        ("Personal Finance 101: Getting Started", date(2024, 1, 15), "10:00 AM", speakers[0], "Comprehensive guide to managing personal finances for beginners.", "completed"),
        ("SIP Investment Strategy for Wealth Building", date(2024, 3, 25), "2:00 PM", speakers[0], "Systematic Investment Plan strategies to grow wealth over time.", "completed"),
        ("Building an Emergency Fund", date(2024, 7, 9), "10:00 AM", speakers[0], "Importance of emergency funds and a step-by-step guide to building one.", "completed"),
        ("Financial Planning for Young Professionals", date(2024, 11, 19), "2:00 PM", speakers[0], "Tailored financial planning tips for early-career professionals.", "completed"),
        ("Year-End Financial Review & 2026 Planning", date(2026, 7, 22), "4:00 PM", speakers[0], "Reviewing 2025 finances and setting goals for 2026.", "upcoming"),
        ("Mutual Funds: A Beginner's Guide", date(2024, 2, 5), "11:00 AM", speakers[1], "Everything you need to know before investing in mutual funds.", "completed"),
        ("Real Estate vs. Mutual Funds", date(2024, 5, 14), "11:00 AM", speakers[1], "A data-driven comparison of real estate and mutual fund returns.", "completed"),
        ("Debt Management and Credit Score Mastery", date(2024, 10, 8), "3:00 PM", speakers[1], "How to manage debt effectively and improve your CIBIL score.", "completed"),
        ("Women and Wealth: Investing with Confidence", date(2026, 6, 15), "11:00 AM", speakers[1], "Empowering women to take charge of their financial future.", "upcoming"),
        ("Tax Planning for Salaried Employees", date(2024, 1, 15), "2:00 PM", speakers[2], "Understanding tax deductions, exemptions, and saving strategies.", "completed"),
        ("Income Tax Filing Made Easy", date(2024, 4, 22), "4:00 PM", speakers[2], "Step-by-step walkthrough for filing your ITR without a CA.", "completed"),
        ("Health Insurance Tax Benefits Explained", date(2024, 8, 20), "10:00 AM", speakers[2], "Maximising 80D deductions and choosing the right health cover.", "completed"),
        ("Advanced Tax Strategies 2026", date(2026, 6, 10), "2:00 PM", speakers[2], "Advanced tax planning techniques for HNIs and business owners.", "upcoming"),
        ("Retirement Planning: Start Early", date(2024, 3, 10), "10:00 AM", speakers[3], "Why starting retirement planning in your 30s makes a huge difference.", "completed"),
        ("NPS and PPF: Long-term Savings Deep Dive", date(2024, 6, 18), "3:00 PM", speakers[3], "Comparing NPS and PPF for long-term wealth creation.", "completed"),
        ("Post-Retirement Income Strategies", date(2025, 1, 7), "11:00 AM", speakers[3], "Ensuring a steady income stream after you stop working.", "completed"),
        ("Stock Market Fundamentals", date(2024, 2, 20), "3:00 PM", speakers[4], "Understanding market mechanics, indices, and company analysis.", "completed"),
        ("Portfolio Diversification Strategies", date(2024, 9, 3), "11:00 AM", speakers[4], "Building a resilient, diversified portfolio across asset classes.", "completed"),
        ("Sectoral Outlook: Where to Invest in 2026", date(2026, 7, 1), "3:00 PM", speakers[4], "Vikram's top sector picks and macro themes for 2026.", "upcoming"),
    ]

    sources = ["email", "social", "direct", "referral"]
    source_weights = [0.40, 0.25, 0.20, 0.15]
    random.seed(42)

    for title, w_date, w_time, speaker, desc, status in webinars_raw:
        webinar = models.Webinar(title=title, date=w_date, time=w_time, speaker_id=speaker.id, description=desc, status=status)
        db.add(webinar)
        db.flush()

        num_reg = random.randint(80, 200) if status == "upcoming" else random.randint(200, 480)
        attendance_prob = random.uniform(0.58, 0.78) if status == "completed" else 0

        for i in range(num_reg):
            src = random.choices(sources, weights=source_weights)[0]
            reg = models.Registration(
                webinar_id=webinar.id,
                attendee_name=f"Participant {i + 1}",
                email=f"participant{i + 1}_{webinar.id}@example.com",
                source=src,
                registered_at=datetime.combine(w_date, datetime.min.time()) - timedelta(days=random.randint(1, 21)),
            )
            db.add(reg)
            db.flush()

            if status == "completed" and random.random() < attendance_prob:
                duration = random.choices(
                    [random.randint(5, 14), random.randint(15, 29), random.randint(30, 44),
                     random.randint(45, 59), random.randint(60, 90)],
                    weights=[0.08, 0.12, 0.22, 0.35, 0.23],
                )[0]
                base = datetime.combine(w_date, datetime.min.time()).replace(hour=10)
                db.add(models.Attendance(
                    webinar_id=webinar.id,
                    registration_id=reg.id,
                    joined_at=base + timedelta(minutes=random.randint(0, 10)),
                    left_at=base + timedelta(minutes=duration),
                    duration_minutes=duration,
                    attended=True,
                ))

    db.commit()
    print("Seeded: speakers + webinars")


if __name__ == "__main__":
    seed_database()
