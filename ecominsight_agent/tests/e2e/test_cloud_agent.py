##  Verificación del Despliegue en Producción (Smoke Testing)

# Una vez que el pipeline de CI/CD finaliza con éxito en Google Cloud Build, el agente queda expuesto de forma segura y elástica en **Google Cloud Run**. 

# Para verificar que el microservicio MCP responde correctamente y mantiene conexiones reactivas mediante Server-Sent Events (SSE) de extremo a extremo, 
# seguimos el siguiente protocolo de prueba:

# Paso 1: Obtener la URL dinámica del servicio en producción
# Dado que Cloud Run genera URLs únicas, consultamos el endpoint activo ejecutando 
# el siguiente comando en la terminal local autenticada con Google Cloud CLI:

# ```powershell
# gcloud run services describe ecominsight-agent-service --region=us-central1 --format="value(status.url)"
# ```

# ejecutamos esto por terminal: uv run python ecominsight_agent\tests\e2e\test_cloud_agent.py
import asyncio
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # URL de tu agente de producción
    url = "https://ecominsight-agent-service-2axrir7upq-uc.a.run.app/sse"
    
    # Extraemos la raíz (ej. https://...app) para no quedarnos atrapados en el bucle infinito del SSE
    base_url = url.replace("/sse", "")
    
    print("Despertando al agente en Cloud Run...")
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            # Hacemos la petición a la raíz. En cuanto el contenedor se encienda, responderá de inmediato
            await client.get(base_url)
    except Exception:
        # Ignoramos el resultado del error (404/405), ya ha cumplido su misión de despertar a GCP
        pass
    
    # Con el contenedor ya activo en los servidores de Google, el handshake de MCP volará
    print("Conectando al agente en Cloud Run...")
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("Realizando handshake de inicialización...")
            await session.initialize()
            
            print("\n--- Solicitando Lista de Herramientas ---")
            tools_response = await session.list_tools()
            print(tools_response)
            
            print("\n--- Ejecutando create_business_report ---")
            result = await session.call_tool(
                name="create_business_report",
                arguments={
                    "title": "Reporte de Producción",
                    "question": "Verificar conexión exitosa en GCP"
                }
            )
            print(result)

if __name__ == "__main__":
    asyncio.run(main())