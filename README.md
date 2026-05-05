# CryptoScope

## GCP Project
- Project ID: bigdata-project-495412
- Region: asia-southeast1
- Zone: asia-southeast1-a

## Buckets
- Bronze: gs://bigdata-project-495412-bronze
- Silver: gs://bigdata-project-495412-silver
- Gold: gs://bigdata-project-495412-gold
- Dead-letter: gs://bigdata-project-495412-deadletter

## Service Accounts
- sa-ingestion@bigdata-project-495412.iam.gserviceaccount.com
- sa-dataproc-etl@bigdata-project-495412.iam.gserviceaccount.com
- sa-dashboard@bigdata-project-495412.iam.gserviceaccount.com
- sa-composer@bigdata-project-495412.iam.gserviceaccount.com

## BigQuery
- Dataset: cryptoscope_analytics

## Secret Manager
- coingecko-api-key

## Architecture
CoinGecko + Kaggle -> GCS Bronze -> Dataproc PySpark -> GCS Silver/Gold -> BigQuery + Cloud SQL -> Streamlit Dashboard
