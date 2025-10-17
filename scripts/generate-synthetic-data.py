#!/usr/bin/env python3
"""
Synthetic E-commerce Sales Data Generator for Azure Batch Processing

Generates realistic sales transaction JSON data for batch processing demonstrations.
"""

import json
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import uuid


class SyntheticDataGenerator:
    """Generates synthetic e-commerce sales transaction data."""

    # Sample data for realistic generation
    FIRST_NAMES = [
        "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
        "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan"
    ]

    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"
    ]

    PRODUCTS = [
        {"name": "Wireless Headphones", "category": "Electronics", "base_price": 79.99},
        {"name": "USB-C Cable", "category": "Electronics", "base_price": 12.99},
        {"name": "Laptop Stand", "category": "Office", "base_price": 45.00},
        {"name": "Mechanical Keyboard", "category": "Electronics", "base_price": 129.99},
        {"name": "Ergonomic Mouse", "category": "Electronics", "base_price": 59.99},
        {"name": "Notebook Set", "category": "Stationery", "base_price": 15.99},
        {"name": "Water Bottle", "category": "Home", "base_price": 24.99},
        {"name": "Desk Lamp", "category": "Office", "base_price": 39.99},
        {"name": "Phone Case", "category": "Accessories", "base_price": 19.99},
        {"name": "Backpack", "category": "Bags", "base_price": 69.99},
        {"name": "Portable Charger", "category": "Electronics", "base_price": 34.99},
        {"name": "Screen Protector", "category": "Accessories", "base_price": 9.99},
        {"name": "Coffee Mug", "category": "Home", "base_price": 12.99},
        {"name": "Desk Organizer", "category": "Office", "base_price": 27.99},
        {"name": "Fitness Tracker", "category": "Wearables", "base_price": 99.99},
    ]

    COUNTRIES = ["USA", "Canada", "UK", "Germany", "France", "Australia", "Japan"]
    STATES = ["CA", "NY", "TX", "FL", "WA", "IL", "PA", "OH", "GA", "NC"]
    PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Apple Pay", "Google Pay"]
    SHIPPING_METHODS = ["Standard", "Express", "Next Day", "International"]

    def __init__(self, seed=None):
        """Initialize generator with optional seed for reproducibility."""
        if seed:
            random.seed(seed)

    def generate_customer(self):
        """Generate a random customer profile."""
        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)

        return {
            "customer_id": f"CUST-{random.randint(10000, 99999)}",
            "name": f"{first_name} {last_name}",
            "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
            "country": random.choice(self.COUNTRIES),
            "state": random.choice(self.STATES) if random.choice(self.COUNTRIES) == "USA" else None
        }

    def generate_line_item(self):
        """Generate a single line item (product) in a transaction."""
        product = random.choice(self.PRODUCTS)
        quantity = random.randint(1, 5)

        # Add some price variation (±20%)
        price_variation = random.uniform(0.8, 1.2)
        unit_price = round(product["base_price"] * price_variation, 2)

        # Occasional discounts
        discount = 0.0
        if random.random() < 0.15:  # 15% chance of discount
            discount = round(random.uniform(0.05, 0.30) * unit_price * quantity, 2)

        subtotal = round(unit_price * quantity - discount, 2)

        return {
            "product_id": f"PROD-{random.randint(1000, 9999)}",
            "product_name": product["name"],
            "category": product["category"],
            "quantity": quantity,
            "unit_price": unit_price,
            "discount": discount,
            "subtotal": subtotal
        }

    def generate_transaction(self, transaction_date=None):
        """Generate a complete transaction."""
        if transaction_date is None:
            # Random date within last 30 days
            days_ago = random.randint(0, 30)
            transaction_date = datetime.now() - timedelta(days=days_ago)

        # Add random time
        transaction_date = transaction_date.replace(
            hour=random.randint(0, 23),
            minute=random.randint(0, 59),
            second=random.randint(0, 59)
        )

        # Generate line items (1-5 items per transaction)
        num_items = random.randint(1, 5)
        line_items = [self.generate_line_item() for _ in range(num_items)]

        # Calculate totals
        subtotal = sum(item["subtotal"] for item in line_items)
        tax_rate = 0.08  # 8% tax
        tax = round(subtotal * tax_rate, 2)

        # Shipping cost based on method
        shipping_method = random.choice(self.SHIPPING_METHODS)
        shipping_cost = {
            "Standard": 5.99,
            "Express": 12.99,
            "Next Day": 24.99,
            "International": 35.99
        }[shipping_method]

        total = round(subtotal + tax + shipping_cost, 2)

        # Generate anomaly: very high value transaction (for anomaly detection demo)
        is_anomaly = False
        if random.random() < 0.01:  # 1% chance
            total = round(total * random.uniform(10, 50), 2)
            is_anomaly = True

        return {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": transaction_date.isoformat() + "Z",
            "customer": self.generate_customer(),
            "line_items": line_items,
            "subtotal": subtotal,
            "tax": tax,
            "shipping_cost": shipping_cost,
            "total": total,
            "payment_method": random.choice(self.PAYMENT_METHODS),
            "shipping_method": shipping_method,
            "status": random.choice(["completed", "completed", "completed", "pending", "cancelled"]),
            "_is_synthetic_anomaly": is_anomaly  # Hidden flag for testing
        }

    def generate_batch(self, count=1000, batch_date=None):
        """Generate a batch of transactions."""
        if batch_date is None:
            batch_date = datetime.now()

        batch_id = f"batch_{batch_date.strftime('%Y%m%d_%H%M%S')}"

        transactions = [
            self.generate_transaction(batch_date)
            for _ in range(count)
        ]

        return {
            "batch_id": batch_id,
            "generated_at": datetime.now().isoformat() + "Z",
            "transaction_count": count,
            "date_range": {
                "start": (batch_date - timedelta(days=30)).isoformat() + "Z",
                "end": batch_date.isoformat() + "Z"
            },
            "transactions": transactions
        }

    def save_batch(self, batch_data, output_path):
        """Save batch data to JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, indent=2, ensure_ascii=False)

        return output_file


def main():
    """Main function to handle CLI arguments and generate data."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic e-commerce sales data for Azure Batch processing"
    )

    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of transactions per batch file (default: 1000)"
    )

    parser.add_argument(
        "--files",
        type=int,
        default=1,
        help="Number of batch files to generate (default: 1)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default="./samples",
        help="Output directory for generated files (default: ./samples)"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (optional)"
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = SyntheticDataGenerator(seed=args.seed)

    print(f"Generating {args.files} batch file(s) with {args.count} transactions each...")
    print(f"Output directory: {output_dir.absolute()}")
    print("-" * 60)

    # Generate files
    for i in range(args.files):
        batch_data = generator.generate_batch(count=args.count)

        # Create filename with index
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"sales_batch_{timestamp}_{i+1:03d}.json"
        output_path = output_dir / filename

        generator.save_batch(batch_data, output_path)

        # Calculate file size
        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        print(f"✓ Generated: {filename}")
        print(f"  - Transactions: {len(batch_data['transactions'])}")
        print(f"  - File size: {file_size_mb:.2f} MB")
        print(f"  - Batch ID: {batch_data['batch_id']}")
        print()

    print("-" * 60)
    print(f"✓ Successfully generated {args.files} file(s)")
    print(f"Total transactions: {args.files * args.count:,}")

    # Generate summary statistics
    print("\nSample Data Preview:")
    print(f"- Products: {len(SyntheticDataGenerator.PRODUCTS)}")
    print(f"- Payment Methods: {len(SyntheticDataGenerator.PAYMENT_METHODS)}")
    print(f"- Shipping Methods: {len(SyntheticDataGenerator.SHIPPING_METHODS)}")
    print(f"- Countries: {len(SyntheticDataGenerator.COUNTRIES)}")

    print("\nNext Steps:")
    print("1. Review generated files in the output directory")
    print("2. Upload to Azure Storage: python scripts/upload-to-storage.py")
    print("3. Submit batch job: python scripts/submit-batch-job.py")


if __name__ == "__main__":
    main()
