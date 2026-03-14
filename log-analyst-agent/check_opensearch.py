import os
from opensearchpy import OpenSearch
from dotenv import load_dotenv

load_dotenv('.env.rag')

endpoint = os.getenv('OPENSEARCH_ENDPOINT')
# Create client
client = OpenSearch(
    hosts=[{'host': endpoint, 'port': 443}],
    use_ssl=True,
    verify_certs=True
)

print(f"Checking cluster: {endpoint}")
try:
    # 1. List all indices and their document counts
    indices = client.cat.indices(format="json")
    print(f"\n{'Index Name':<40} {'Docs':<10} {'Status':<10}")
    print("-" * 65)
    for idx in indices:
        if not idx['index'].startswith('.'): # Skip system indices
            print(f"{idx['index']:<40} {idx['docs.count']:<10} {idx['status']:<10}")

    # 2. Check the most recent log in your specific patterns
    patterns = ["appgate-logs-*", "security-logs-*", "cwl-*", "paloalto-*"]
    print("\nMost Recent Log per Pattern:")
    print("-" * 65)
    for p in patterns:
        try:
            res = client.search(index=p, body={
                "size": 1,
                "sort": [{"@timestamp": {"order": "desc"}}]
            })
            if res['hits']['hits']:
                ts = res['hits']['hits'][0]['_source'].get('@timestamp', 'No @timestamp field')
                print(f"{p:<40} {ts}")
            else:
                print(f"{p:<40} No logs found in this pattern")
        except Exception:
            print(f"{p:<40} Index/Pattern does not exist")

except Exception as e:
    print(f"Error connecting: {e}")
