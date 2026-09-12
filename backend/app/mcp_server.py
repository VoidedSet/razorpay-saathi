from mcp.server.fastmcp import FastMCP
from app import db
import json

# Create the MCP Server
mcp = FastMCP("Razorpay Saathi Catalog")

@mcp.tool()
def search_catalog(
    query: str | None = "",
    limit: int | None = 6,
    category: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    specs_filter: str | None = None
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
        query=query or "", 
        limit=limit or 6, 
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

@mcp.tool()
def add_to_cart(session_id: str, product_id: str, quantity: int = 1) -> str:
    """
    Add a product to the user's cart.
    
    Args:
        session_id: Unique session ID for the user's cart.
        product_id: The ID of the product.
        quantity: Number of items to add (default 1).
    """
    success = db.add_to_cart(session_id, product_id, quantity)
    if success:
        return f"Successfully added {quantity} of {product_id} to cart."
    return f"Failed to add {product_id} to cart (product might not exist)."

@mcp.tool()
def view_cart(session_id: str) -> str:
    """
    View the current contents of the user's cart.
    
    Args:
        session_id: Unique session ID for the user's cart.
    """
    cart = db.get_cart(session_id)
    return json.dumps(cart, indent=2)

@mcp.tool()
def clear_cart(session_id: str) -> str:
    """
    Clear all items from the user's cart.
    
    Args:
        session_id: Unique session ID for the user's cart.
    """
    db.clear_cart(session_id)
    return "Cart cleared successfully."

@mcp.tool()
def get_offers(amount_inr: int) -> str:
    """
    Get applicable Razorpay offers for a given cart total amount.
    
    Args:
        amount_inr: The total checkout amount in INR.
    """
    offers = db.get_razorpay_offers(amount_inr)
    if not offers:
        return "No offers applicable for this amount."
    return json.dumps(offers, indent=2)

@mcp.tool()
def checkout(session_id: str) -> str:
    """
    Generate a Razorpay payment link for the current cart.
    
    Args:
        session_id: Unique session ID for the user's cart.
    """
    cart = db.get_cart(session_id)
    if not cart:
        return "Error: Cart is empty."
    
    total = sum(item.get("price", 0) * item.get("qty", 1) for item in cart)
    link = db.get_payment_link(amount_inr=total, reference_id=f"checkout_{session_id}")
    return json.dumps(link, indent=2)

if __name__ == "__main__":
    mcp.run()
