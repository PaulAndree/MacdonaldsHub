# Source this file to point integration tests at the throwaway `test` profile services:
#   source scripts/test-env.sh
# The Azurite key below is the publicly documented development key, not a secret.
export TEST_DATABASE_URL="postgresql+psycopg://postgres:${POSTGRES_PASSWORD:-localdev}@127.0.0.1:55432/deliveryhub_test"
export TEST_AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10100/devstoreaccount1;"
export TEST_MAILPIT_URL="http://127.0.0.1:8025"
export REQUIRE_INTEGRATION=1
