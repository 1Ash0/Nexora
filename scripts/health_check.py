import sys
import time
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import redis
import psycopg2

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def print_status(service, status, msg=""):
    if status:
        print(f"{GREEN}[OK] {service} running{RESET} {msg}")
    else:
        print(f"{RED}[FAIL] {service} failed{RESET} {msg}")

def test_neo4j():
    try:
        driver = GraphDatabase.driver("bolt://127.0.0.1:7687", auth=("neo4j", "research123"))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception as e:
        print_status("Neo4j", False, str(e))
        return False

def test_qdrant():
    try:
        client = QdrantClient(host="127.0.0.1", port=6333)
        client.get_collections()
        return True
    except Exception as e:
        print_status("Qdrant", False, str(e))
        return False

def test_redis():
    try:
        r = redis.Redis(host='127.0.0.1', port=6379, db=0)
        r.ping()
        return True
    except Exception as e:
        print_status("Redis", False, str(e))
        return False

def test_postgres():
    try:
        conn = psycopg2.connect(
            dbname="research_db",
            user="research",
            password="research123",
            host="127.0.0.1",
            port="5432"
        )
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
