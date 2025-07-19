from requests import post
from airflow import DAG 
from airflow.providers.http.operators.http import HttpOperator
from airflow.decorators import task 
from airflow.providers.postgres.hooks.postgres import PostgresHook
import json 
from datetime import datetime, timedelta

## Define DAG

with DAG(
    dag_id='nasa_apod_postgres',
    start_date= datetime.now() - timedelta(days=1),
    schedule='@daily'
    
) as dag:
    
    # Step 1: Create the table if it doesnt exist
    @task 
    def create_table():
        ## Initialize the Postgreshook 
        postgres_hook = PostgresHook(postgres_conn_id='postgres_connection')
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS apod_data (
          id SERIAL PRIMARY KEY,
          title VARCHAR(255),
          explanation TEXT,
          url TEXT,
          date DATE,
          media_type VARCHAR(50)  
        );
        """
        postgres_hook.run(create_table_query)
        
    # Step 2: Extract the NASA API Data  Picture of the Day
    extract_apod= HttpOperator(
        task_id="extract_apod",
        http_conn_id='nasa_api', ## Connection ID defined in Airflow for NASA API
        endpoint='planetary/apod', ## NASA API Endpoint 
        method="GET",
        data={"api_key":"{{conn.nasa_api.extra_dejson.api_key}}"},
        response_filter=lambda response:response.json()
    )
    
    # Step 3: Transform the data 
    @task 
    def transform_apod_data(response):
        apod_data = {
            'title': response.get('title', ''),
            'explanation': response.get('explanation', ''),
            'url': response.get('url', ''),
            'date': response.get('date', ''),
            'media_type': response.get('media_type', '')
        }

        return apod_data 
    
    # Step 4: Load the data into Postgres SQL
    @task 
    def load_data_to_postgres(apod_data):
        postgres_hook= PostgresHook(postgres_conn_id='postgres_connection')
        
        insert_query = """
        INSERT INTO apod_data (title, explanation, url, date, media_type)
        VALUES (%s, %s, %s, %s, %s);
        """
        
        postgres_hook.run(insert_query, parameters=(
            apod_data['title'],
            apod_data['explanation'],
            apod_data['url'],
            apod_data['date'],
            apod_data['media_type']
        ))
    # Step 5: Verify the data DB Viewer 
    
    # Step 6: Define the task dependency 
    # Extract 
    create_table() >> extract_apod 
    api_response = extract_apod.output
    # Transform
    transformed_data = transform_apod_data(api_response )
    # Load
    load_data_to_postgres(transformed_data)
