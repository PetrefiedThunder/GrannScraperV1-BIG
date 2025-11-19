"""
Apache Airflow Integration Example

This DAG shows how to integrate GrandmaScrape with Apache Airflow for
scheduled scraping jobs.

Installation:
    pip install apache-airflow

Usage:
    1. Place this file in your Airflow DAGs folder
    2. Ensure GrandmaScrape API server is running
    3. Airflow will execute the DAG on schedule
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
import requests


# Default arguments for the DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email': ['alerts@example.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Configuration
SCRAPER_API_URL = "http://localhost:8000/api/v1"
TARGET_URL = "https://example.com/products"
QUALITY_THRESHOLD = 0.8


def scrape_website(**context):
    """Task 1: Scrape the website using GrandmaScrape API."""
    print(f"Starting scrape of {TARGET_URL}")

    # Start scrape job
    response = requests.post(
        f"{SCRAPER_API_URL}/analyze",
        json={"url": TARGET_URL, "max_pages": 1}
    )
    response.raise_for_status()
    analysis = response.json()

    # Create job from analysis
    job_data = {
        "job": {
            "id": f"airflow_{context['ds_nodash']}",
            "name": f"Daily scrape - {context['ds']}",
            "start_url": TARGET_URL,
            "item_selector": analysis.get('item_selector'),
            "fields": analysis.get('fields', {}),
            "max_pages": 50,
            "export": {"format": "json"},
            "enabled": True,
        }
    }

    response = requests.post(f"{SCRAPER_API_URL}/jobs", json=job_data)
    response.raise_for_status()
    job_id = response.json()['job_id']

    # Run job
    response = requests.post(
        f"{SCRAPER_API_URL}/jobs/{job_id}/run",
        params={"concurrent": True, "incremental": True}
    )
    response.raise_for_status()

    # Wait for completion (simplified - in production use sensors)
    import time
    max_wait = 600  # 10 minutes
    start_time = time.time()

    while time.time() - start_time < max_wait:
        response = requests.get(f"{SCRAPER_API_URL}/jobs/{job_id}/status")
        status = response.json()

        if not status['is_running']:
            break

        time.sleep(10)

    # Push job_id to XCom for next tasks
    context['task_instance'].xcom_push(key='job_id', value=job_id)

    print(f"Scrape completed! Job ID: {job_id}")
    return job_id


def check_data_quality(**context):
    """Task 2: Check data quality."""
    job_id = context['task_instance'].xcom_pull(key='job_id', task_ids='scrape_website')

    print(f"Checking data quality for job {job_id}")

    # Get quality report
    response = requests.post(f"{SCRAPER_API_URL}/jobs/{job_id}/quality-check")
    response.raise_for_status()
    quality_data = response.json()

    quality_score = quality_data['quality_report']['quality_score']
    print(f"Quality score: {quality_score:.1%}")

    # Push to XCom
    context['task_instance'].xcom_push(key='quality_score', value=quality_score)

    # Fail if quality is too low
    if quality_score < QUALITY_THRESHOLD:
        raise ValueError(
            f"Data quality ({quality_score:.1%}) below threshold ({QUALITY_THRESHOLD:.1%})"
        )

    return quality_score


def detect_anomalies(**context):
    """Task 3: Detect anomalies in scraped data."""
    job_id = context['task_instance'].xcom_pull(key='job_id', task_ids='scrape_website')

    print(f"Detecting anomalies for job {job_id}")

    response = requests.post(f"{SCRAPER_API_URL}/jobs/{job_id}/detect-anomalies")
    response.raise_for_status()
    anomaly_data = response.json()

    severity = anomaly_data['severity']
    anomaly_score = anomaly_data['anomaly_score']

    print(f"Anomaly severity: {severity}")
    print(f"Anomaly score: {anomaly_score:.1%}")

    # Push to XCom
    context['task_instance'].xcom_push(key='anomaly_severity', value=severity)
    context['task_instance'].xcom_push(key='anomaly_score', value=anomaly_score)

    # Warn if high severity
    if severity in ['high', 'critical']:
        print(f"WARNING: {severity.upper()} severity anomalies detected!")

    return severity


def export_to_database(**context):
    """Task 4: Export results to database (example)."""
    job_id = context['task_instance'].xcom_pull(key='job_id', task_ids='scrape_website')

    print(f"Exporting results for job {job_id}")

    # Get results
    response = requests.get(
        f"{SCRAPER_API_URL}/jobs/{job_id}/results",
        params={"limit": 10000}
    )
    response.raise_for_status()
    data = response.json()

    items = data['items']
    print(f"Retrieved {len(items)} items")

    # Example: Export to PostgreSQL (pseudo-code)
    # import psycopg2
    # conn = psycopg2.connect(DATABASE_URL)
    # cursor = conn.cursor()
    # for item in items:
    #     cursor.execute("INSERT INTO products (...) VALUES (%s, %s, ...)", (item['title'], item['price']))
    # conn.commit()
    # conn.close()

    print(f"Exported {len(items)} items to database")
    return len(items)


def send_summary_report(**context):
    """Task 5: Generate and return summary report."""
    job_id = context['task_instance'].xcom_pull(key='job_id', task_ids='scrape_website')
    quality_score = context['task_instance'].xcom_pull(key='quality_score', task_ids='check_data_quality')
    anomaly_severity = context['task_instance'].xcom_pull(key='anomaly_severity', task_ids='detect_anomalies')
    anomaly_score = context['task_instance'].xcom_pull(key='anomaly_score', task_ids='detect_anomalies')

    # Get job status
    response = requests.get(f"{SCRAPER_API_URL}/jobs/{job_id}/status")
    status = response.json()

    report = f"""
Daily Scraping Report - {context['ds']}
{'=' * 60}

Job ID: {job_id}
Target URL: {TARGET_URL}

RESULTS:
  Items Scraped: {status.get('items_scraped', 0)}
  Pages Visited: {status.get('pages_visited', 0)}
  Duration: {status.get('duration', 0):.2f}s
  Errors: {status.get('errors', 0)}

QUALITY:
  Quality Score: {quality_score:.1%}
  Status: {"✅ PASS" if quality_score >= QUALITY_THRESHOLD else "❌ FAIL"}

ANOMALIES:
  Severity: {anomaly_severity.upper()}
  Anomaly Score: {anomaly_score:.1%}
  Status: {"✅ OK" if anomaly_severity in ['low', 'medium'] else "⚠️ WARNING"}

{'=' * 60}
    """

    print(report)
    return report


# Define the DAG
dag = DAG(
    'grandmascrape_daily_scraping',
    default_args=default_args,
    description='Daily web scraping with GrandmaScrape',
    schedule_interval='0 2 * * *',  # Run daily at 2 AM
    catchup=False,
    tags=['scraping', 'data-collection'],
)

# Define tasks
t1 = PythonOperator(
    task_id='scrape_website',
    python_callable=scrape_website,
    dag=dag,
)

t2 = PythonOperator(
    task_id='check_data_quality',
    python_callable=check_data_quality,
    dag=dag,
)

t3 = PythonOperator(
    task_id='detect_anomalies',
    python_callable=detect_anomalies,
    dag=dag,
)

t4 = PythonOperator(
    task_id='export_to_database',
    python_callable=export_to_database,
    dag=dag,
)

t5 = PythonOperator(
    task_id='send_summary_report',
    python_callable=send_summary_report,
    dag=dag,
)

# Define task dependencies
t1 >> [t2, t3] >> t4 >> t5

# Alternative: Send email report
# t_email = EmailOperator(
#     task_id='send_email_report',
#     to='data-team@example.com',
#     subject='Daily Scraping Report - {{ ds }}',
#     html_content='{{ task_instance.xcom_pull(task_ids="send_summary_report") }}',
#     dag=dag,
# )
# t5 >> t_email
