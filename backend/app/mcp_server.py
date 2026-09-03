from mcp.server.fastmcp import FastMCP
from app import db
import json

# Create the MCP Server
mcp = FastMCP("Razorpay Saathi Catalog")

@mcp.tool()
def search_catalog(
    query: str = "",
    limit: int = 6,
    category: str = None,
    min_price: int = None,
    max_price: int = None,
    specs_filter: str = None
) -> str:
    """
    Search the Razorpay Saathi catalog for products.
    
    Args:
        query: Optional keyword search string (e.g. "sneakers", "yeezy").
        limit: Max number of results to return (default 6).
        category: Optional exact category filter (e.g. "sneakers", "apparel", "accessories").
        min_price: Minimum price in INR.
        max_price: Maximum price in INR.
        specs_filter: Optional JSON string of exact specs to match (e.g. '{"color": "Black", "size_uk": 9}').
    """
    specs_dict = None
    if specs_filter:
        try:
            specs_dict = json.loads(specs_filter)
        except json.JSONDecodeError:
            return "Error: specs_filter must be a valid JSON string."
            
    results = db.search_products(
        query=query, 
        limit=limit, 
        category=category, 
        min_price=min_price, 
        max_price=max_price, 
        specs_filter=specs_dict
    )
    
    if not results:
        return "No products found matching the criteria."
        
    return json.dumps(results, indent=2)

@mcp.tool()
def get_product(product_id: str) -> str:
    """
    Retrieve full details for a specific product by its ID.
    
    Args:
        product_id: The ID of the product (e.g., 'prod_01')
    """
    product = db.get_product(product_id)
    if not product:
        return f"Error: Product with ID '{product_id}' not found."
    return json.dumps(product, indent=2)

if __name__ == "__main__":
    mcp.run()
