from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
from service_a.app.config import settings
from service_a.app.services.service_b_client import service_b_client

app = FastAPI(
    title="Service A - API Gateway / Backend",
    description="Public entrypoint for client requests. Authenticates requests and queries Service B."
)

def verify_client_token(request: Request):
    """
    Custom security dependency that validates the client Bearer token.
    Raises 401 Unauthorized for both missing and invalid keys.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )
    token = auth_header.split(" ", 1)[1]
    if token != settings.client_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing token"
        )

@app.get(
    "/api/v1/market-snapshot",
    dependencies=[Depends(verify_client_token)]
)
def get_market_snapshot(
    symbol: str = Query(..., min_length=1, description="Ticker symbol to fetch market snapshot for")
):
    """
    Public endpoint to retrieve normalized stock/crypto snapshots.
    Validates client credentials and proxies requests to Service B.
    """
    try:
        snapshot = service_b_client.fetch_market_data(symbol)
        return snapshot
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gateway routing error: {str(e)}"
        )
