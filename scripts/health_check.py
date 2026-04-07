import sys
import time
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import redis
import psycopg2

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

from backend.config.settings import settings

def print_status(service, status, msg=""):
    if status:
        print(f"{GREEN}[OK] {service} running{RESET} {msg}")
    else:
        print(f"{RED}[FAIL] {service} failed{RESET} {msg}")

def test_neo4j():
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception as e:
        print_status("Neo4j", False, str(e))
        return False

def test_qdrant():
    try:
        client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        client.get_collections()
        return True
    except Exception as e:
        print_status("Qdrant", False, str(e))
        return False

def test_redis():
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        return True
    except Exception as e:
        print_status("Redis", False, str(e))
        return False

def test_postgres():
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.close()
        return True
    except Exception as e:
        print_status("PostgreSQL", False, str(e))
        return False

def main():
    print("Running Health Checks against 127.0.0.1...")
    results = [
        test_neo4j(),
        test_qdrant(),
        test_redis(),
        test_postgres()
    ]
    
    if test_neo4j(): print_status("Neo4j", True)
    if test_qdrant(): print_status("Qdrant", True)
    if test_redis(): print_status("Redis", True)
    if test_postgres(): print_status("PostgreSQL", True)
    
    if all(results):
        print("\nAll expected services are up and running!")
        sys.exit(0)
    else:
        print("\nSome services failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
