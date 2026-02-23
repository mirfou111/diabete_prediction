import joblib, pandas as pd
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Diabetes_AI")
model = joblib.load('diabetes_model.pkl')
scaler = joblib.load('scaler.pkl')

@mcp.tool()
def check_diabetes(age: float, glucose: float, bmi: float):
    """Outil IA pour le diagnostic du diabète via MCP."""
    df = pd.DataFrame([[1, age, 0, 0, 0, bmi, 5.5, glucose]])
    pred = model.predict(scaler.transform(df))[0]
    return "Risque détecté" if pred == 1 else "Risque faible"

if __name__ == "__main__":
    # Crucial pour Docker : transport SSE sur le port 8000
    mcp.run(transport='sse')
