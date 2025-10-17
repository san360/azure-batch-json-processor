"""
JSON Processor - Core Business Logic

Processes e-commerce sales transaction JSON data with validation,
aggregation, analytics, and anomaly detection.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict


logger = logging.getLogger(__name__)


class JSONProcessor:
    """Processes sales transaction JSON data."""

    # Validation thresholds
    MAX_UNIT_PRICE = 10000.0
    MAX_QUANTITY = 100
    MAX_TOTAL = 100000.0
    ANOMALY_THRESHOLD = 5000.0  # Transactions above this are flagged

    def __init__(self):
        """Initialize the processor."""
        self.stats = {
            "total_transactions": 0,
            "valid_transactions": 0,
            "invalid_transactions": 0,
            "processing_errors": 0
        }

    def validate_transaction(self, transaction: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a single transaction.

        Args:
            transaction: Transaction dictionary

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        required_fields = [
            "transaction_id", "timestamp", "customer", "line_items",
            "subtotal", "tax", "total", "payment_method", "status"
        ]

        for field in required_fields:
            if field not in transaction:
                errors.append(f"Missing required field: {field}")

        if errors:
            return False, errors

        # Validate customer
        customer = transaction.get("customer", {})
        if not customer.get("customer_id"):
            errors.append("Missing customer_id")
        if not customer.get("email"):
            errors.append("Missing customer email")

        # Validate line items
        line_items = transaction.get("line_items", [])
        if not line_items:
            errors.append("No line items in transaction")

        for idx, item in enumerate(line_items):
            if item.get("unit_price", 0) > self.MAX_UNIT_PRICE:
                errors.append(f"Line item {idx}: unit_price exceeds maximum")
            if item.get("quantity", 0) > self.MAX_QUANTITY:
                errors.append(f"Line item {idx}: quantity exceeds maximum")
            if item.get("quantity", 0) <= 0:
                errors.append(f"Line item {idx}: invalid quantity")

        # Validate totals
        total = transaction.get("total", 0)
        if total > self.MAX_TOTAL:
            errors.append(f"Total amount exceeds maximum: {total}")
        if total <= 0:
            errors.append(f"Invalid total amount: {total}")

        # Validate timestamp
        try:
            datetime.fromisoformat(transaction["timestamp"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            errors.append("Invalid timestamp format")

        is_valid = len(errors) == 0
        return is_valid, errors

    def calculate_aggregates(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate aggregate statistics from transactions.

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Dictionary of aggregate statistics
        """
        logger.info(f"Calculating aggregates for {len(transactions)} transactions")

        total_revenue = 0.0
        total_tax = 0.0
        total_shipping = 0.0
        transaction_count = 0
        completed_count = 0

        # Category and product tracking
        category_revenue = defaultdict(float)
        product_revenue = defaultdict(float)
        product_quantity = defaultdict(int)

        # Customer tracking
        customer_revenue = defaultdict(float)
        customer_order_count = defaultdict(int)

        # Payment and shipping methods
        payment_methods = defaultdict(int)
        shipping_methods = defaultdict(int)

        # Status tracking
        status_counts = defaultdict(int)

        for transaction in transactions:
            try:
                # Skip invalid transactions
                is_valid, _ = self.validate_transaction(transaction)
                if not is_valid:
                    continue

                transaction_count += 1
                status = transaction.get("status", "unknown")
                status_counts[status] += 1

                if status == "completed":
                    completed_count += 1
                    total = transaction.get("total", 0)
                    total_revenue += total
                    total_tax += transaction.get("tax", 0)
                    total_shipping += transaction.get("shipping_cost", 0)

                    # Customer stats
                    customer_id = transaction.get("customer", {}).get("customer_id")
                    if customer_id:
                        customer_revenue[customer_id] += total
                        customer_order_count[customer_id] += 1

                    # Line item stats
                    for item in transaction.get("line_items", []):
                        category = item.get("category", "Unknown")
                        product_name = item.get("product_name", "Unknown")
                        subtotal = item.get("subtotal", 0)
                        quantity = item.get("quantity", 0)

                        category_revenue[category] += subtotal
                        product_revenue[product_name] += subtotal
                        product_quantity[product_name] += quantity

                # Payment and shipping methods (all statuses)
                payment_methods[transaction.get("payment_method", "Unknown")] += 1
                shipping_methods[transaction.get("shipping_method", "Unknown")] += 1

            except Exception as e:
                logger.error(f"Error processing transaction: {str(e)}")
                continue

        # Calculate averages
        avg_order_value = total_revenue / completed_count if completed_count > 0 else 0
        avg_tax = total_tax / completed_count if completed_count > 0 else 0
        avg_shipping = total_shipping / completed_count if completed_count > 0 else 0

        # Top customers (by revenue)
        top_customers = sorted(
            customer_revenue.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Top products (by revenue)
        top_products_revenue = sorted(
            product_revenue.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Top products (by quantity)
        top_products_quantity = sorted(
            product_quantity.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "summary": {
                "total_transactions": transaction_count,
                "completed_transactions": completed_count,
                "total_revenue": round(total_revenue, 2),
                "total_tax": round(total_tax, 2),
                "total_shipping": round(total_shipping, 2),
                "average_order_value": round(avg_order_value, 2),
                "average_tax": round(avg_tax, 2),
                "average_shipping": round(avg_shipping, 2)
            },
            "status_breakdown": dict(status_counts),
            "revenue_by_category": {k: round(v, 2) for k, v in sorted(category_revenue.items(), key=lambda x: x[1], reverse=True)},
            "top_customers": [
                {"customer_id": cid, "total_revenue": round(rev, 2), "order_count": customer_order_count[cid]}
                for cid, rev in top_customers
            ],
            "top_products_by_revenue": [
                {"product": prod, "revenue": round(rev, 2), "quantity_sold": product_quantity[prod]}
                for prod, rev in top_products_revenue
            ],
            "top_products_by_quantity": [
                {"product": prod, "quantity_sold": qty, "revenue": round(product_revenue[prod], 2)}
                for prod, qty in top_products_quantity
            ],
            "payment_methods": dict(payment_methods),
            "shipping_methods": dict(shipping_methods)
        }

    def detect_anomalies(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies in transactions.

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Dictionary of anomaly detection results
        """
        logger.info("Detecting anomalies in transactions")

        high_value_transactions = []
        suspicious_patterns = []
        duplicate_check = set()
        rapid_transactions = defaultdict(list)

        for transaction in transactions:
            try:
                transaction_id = transaction.get("transaction_id")
                total = transaction.get("total", 0)
                timestamp = transaction.get("timestamp", "")
                customer_id = transaction.get("customer", {}).get("customer_id")

                # Check for high-value transactions
                if total > self.ANOMALY_THRESHOLD:
                    high_value_transactions.append({
                        "transaction_id": transaction_id,
                        "total": total,
                        "timestamp": timestamp,
                        "customer_id": customer_id
                    })

                # Check for duplicate transaction IDs
                if transaction_id in duplicate_check:
                    suspicious_patterns.append({
                        "type": "duplicate_transaction_id",
                        "transaction_id": transaction_id,
                        "description": "Transaction ID appears multiple times"
                    })
                duplicate_check.add(transaction_id)

                # Track transactions by customer for rapid transaction detection
                if customer_id:
                    rapid_transactions[customer_id].append({
                        "transaction_id": transaction_id,
                        "timestamp": timestamp,
                        "total": total
                    })

                # Check for unusual quantity patterns
                for item in transaction.get("line_items", []):
                    if item.get("quantity", 0) > 20:
                        suspicious_patterns.append({
                            "type": "high_quantity",
                            "transaction_id": transaction_id,
                            "product": item.get("product_name"),
                            "quantity": item.get("quantity"),
                            "description": f"Unusually high quantity: {item.get('quantity')}"
                        })

            except Exception as e:
                logger.error(f"Error detecting anomalies: {str(e)}")
                continue

        # Check for customers with many transactions (possible fraud)
        frequent_customers = [
            {
                "customer_id": cid,
                "transaction_count": len(txns),
                "total_spent": sum(t["total"] for t in txns)
            }
            for cid, txns in rapid_transactions.items()
            if len(txns) > 10
        ]

        return {
            "high_value_transactions": {
                "count": len(high_value_transactions),
                "threshold": self.ANOMALY_THRESHOLD,
                "transactions": high_value_transactions[:20]  # Limit to top 20
            },
            "suspicious_patterns": {
                "count": len(suspicious_patterns),
                "patterns": suspicious_patterns[:20]  # Limit to top 20
            },
            "frequent_customers": {
                "count": len(frequent_customers),
                "customers": frequent_customers
            }
        }

    def process(self, json_data: str) -> Dict[str, Any]:
        """
        Main processing function.

        Args:
            json_data: JSON string containing batch data

        Returns:
            Dictionary with processing results
        """
        logger.info("Starting JSON processing")
        start_time = datetime.now()

        try:
            # Parse JSON
            data = json.loads(json_data)
            logger.info(f"Parsed JSON data: {len(json_data)} characters")

            # Extract transactions
            transactions = data.get("transactions", [])
            batch_id = data.get("batch_id", "unknown")
            transaction_count = len(transactions)

            logger.info(f"Processing batch {batch_id} with {transaction_count} transactions")

            # Validate all transactions
            validation_results = []
            valid_transactions = []

            for idx, transaction in enumerate(transactions):
                is_valid, errors = self.validate_transaction(transaction)

                if is_valid:
                    self.stats["valid_transactions"] += 1
                    valid_transactions.append(transaction)
                else:
                    self.stats["invalid_transactions"] += 1
                    validation_results.append({
                        "transaction_index": idx,
                        "transaction_id": transaction.get("transaction_id", "unknown"),
                        "errors": errors
                    })

            self.stats["total_transactions"] = transaction_count

            # Calculate aggregates
            aggregates = self.calculate_aggregates(valid_transactions)

            # Detect anomalies
            anomalies = self.detect_anomalies(valid_transactions)

            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Build result
            result = {
                "batch_id": batch_id,
                "input_transaction_count": transaction_count,
                "processed_at": end_time.isoformat() + "Z",
                "processing_time_seconds": round(processing_time, 2),
                "validation": {
                    "total_transactions": self.stats["total_transactions"],
                    "valid_transactions": self.stats["valid_transactions"],
                    "invalid_transactions": self.stats["invalid_transactions"],
                    "validation_errors": validation_results[:50]  # Limit to first 50
                },
                "analytics": aggregates,
                "anomalies": anomalies,
                "metadata": {
                    "processor_version": "1.0.0",
                    "input_batch_id": batch_id,
                    "original_generated_at": data.get("generated_at", "unknown")
                }
            }

            logger.info(f"Processing completed in {processing_time:.2f} seconds")
            logger.info(f"Valid: {self.stats['valid_transactions']}, Invalid: {self.stats['invalid_transactions']}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            return {
                "error": "JSON parsing failed",
                "details": str(e),
                "processed_at": datetime.now().isoformat() + "Z"
            }

        except Exception as e:
            logger.error(f"Processing error: {str(e)}", exc_info=True)
            return {
                "error": "Processing failed",
                "details": str(e),
                "processed_at": datetime.now().isoformat() + "Z"
            }
