import json
import re
from typing import Optional, List, Dict

class PartsDatabase:
    def __init__(self, db_path: str = "master_parts_db.json", inventory_path: str = "inventory_data.json"):
        """Load the master parts database and your inventory"""
        with open(db_path, 'r', encoding='utf-8') as f:
            self.master_db = json.load(f)
        
        try:
            with open(inventory_path, 'r', encoding='utf-8') as f:
                self.inventory = json.load(f)
        except FileNotFoundError:
            self.inventory = []
            print("Warning: inventory_data.json not found")
    
    def clean_part_number(self, text: str) -> str:
        """Clean a part number for searching"""
        return re.sub(r'[^a-zA-Z0-9]', '', text).lower()
    
    def search_master_db(self, query: str) -> Optional[Dict]:
        """Search the master database for a part number"""
        clean_query = self.clean_part_number(query)
        
        # Search all categories
        for category, parts in self.master_db.items():
            for part in parts:
                # Check primary part number
                if self.clean_part_number(part['part_number']) == clean_query:
                    return {**part, 'found_in': category}
                
                # Check OEM numbers
                for oem in part.get('oem_numbers', []):
                    if self.clean_part_number(oem) == clean_query:
                        return {**part, 'found_in': category}
                
                # Check cross references
                for cross in part.get('cross_references', []):
                    if self.clean_part_number(cross) == clean_query:
                        return {**part, 'found_in': category, 'matched_as': 'alternative'}
        
        return None
    
    def search_inventory(self, part_number: str) -> Optional[Dict]:
        """Search your inventory for a part"""
        clean_query = self.clean_part_number(part_number)
        
        for item in self.inventory:
            if self.clean_part_number(str(item.get('sku', ''))) == clean_query:
                return item
            if self.clean_part_number(item.get('name', '')) == clean_query:
                return item
            if clean_query in self.clean_part_number(item.get('description', '')):
                return item
        
        return None
    
    def find_alternatives_in_inventory(self, part_data: Dict) -> List[Dict]:
        """Find alternative parts in your inventory based on cross-references"""
        alternatives = []
        
        # Check all cross-references against inventory
        for cross_ref in part_data.get('cross_references', []):
            for item in self.inventory:
                item_name = self.clean_part_number(item.get('name', ''))
                if self.clean_part_number(cross_ref) in item_name or item_name in self.clean_part_number(cross_ref):
                    if item not in alternatives:
                        alternatives.append(item)
        
        return alternatives
    
    def lookup_part(self, query: str) -> Dict:
        """Main lookup function - returns comprehensive results"""
        result = {
            'query': query,
            'found_in_master': False,
            'found_in_inventory': False,
            'master_data': None,
            'inventory_data': None,
            'alternatives': [],
            'message': ''
        }
        
        # Search master database
        master_result = self.search_master_db(query)
        if master_result:
            result['found_in_master'] = True
            result['master_data'] = master_result
        
        # Search inventory
        inventory_result = self.search_inventory(query)
        if inventory_result:
            result['found_in_inventory'] = True
            result['inventory_data'] = inventory_result
        
        # Find alternatives in inventory
        if master_result:
            result['alternatives'] = self.find_alternatives_in_inventory(master_result)
        
        # Generate response message
        result['message'] = self.format_response(result)
        
        return result
    
    def format_response(self, result: Dict) -> str:
        """Format a human-readable response for WhatsApp"""
        lines = []
        
        if result['found_in_master']:
            part = result['master_data']
            lines.append(f"🔍 *{part['part_number']}*")
            lines.append(f"Type: {part['type'].replace('_', ' ').title()}")
            lines.append(f"Category: {part['category']}")
            
            # Dimensions
            if part.get('dimensions'):
                lines.append("\n📏 *Dimensions:*")
                for key, value in part['dimensions'].items():
                    label = key.replace('_', ' ').title()
                    lines.append(f"  • {label}: {value}mm")
            
            # Fitment
            if part.get('fitment'):
                lines.append("\n🚗 *Fitment:*")
                for fit in part['fitment'][:5]:  # Show first 5
                    lines.append(f"  • {fit['make']} {fit['model']} ({fit.get('years', fit.get('application', ''))})")
            
            # Notes
            if part.get('notes'):
                lines.append(f"\n📝 {part['notes']}")
            
            # Cross references
            if part.get('cross_references'):
                lines.append("\n🔄 *Known Alternatives:*")
                for alt in part['cross_references'][:5]:
                    lines.append(f"  • {alt}")
        
        # Inventory status
        lines.append("\n---\n📦 *Our Stock Status:*")
        if result['found_in_inventory']:
            inv = result['inventory_data']
            lines.append(f"✅ *IN STOCK - KSh {inv.get('price', 'N/A')}*")
            lines.append(f"   Qty: {inv.get('stock', 0)} | SKU: {inv.get('sku', 'N/A')}")
        else:
            lines.append("❌ Exact match NOT in stock")
        
        # Alternatives in stock
        if result['alternatives']:
            lines.append("\n🟢 *Alternatives Available:*")
            for alt in result['alternatives'][:3]:
                lines.append(f"  • {alt['name']} (SKU: {alt['sku']}, KSh {alt['price']}, Qty: {alt['stock']})")
        elif not result['found_in_inventory']:
            lines.append("⚠️ No alternatives found in stock")
        
        return '\n'.join(lines)


# ===================== WHATSAPP BOT INTEGRATION =====================
# This would be used with Twilio/WhatsApp API

def whatsapp_webhook(request_data):
    """
    Handle incoming WhatsApp message.
    This would be deployed as a webhook endpoint.
    """
    # Extract message from WhatsApp webhook
    incoming_message = request_data.get('Body', '').strip()
    sender = request_data.get('From', '')
    
    # Initialize database
    db = PartsDatabase('master_parts_db.json', 'inventory_data.json')
    
    # Lookup the part
    result = db.lookup_part(incoming_message)
    
    # Return response
    return {
        'to': sender,
        'message': result['message']
    }


# ===================== COMMAND LINE TEST =====================
if __name__ == "__main__":
    db = PartsDatabase('master_parts_db.json', 'inventory_data.json')
    
    print("=" * 50)
    print("PARTS LOOKUP SYSTEM - Command Line Test")
    print("=" * 50)
    
    while True:
        query = input("\nEnter part number (or 'quit'): ").strip()
        if query.lower() == 'quit':
            break
        
        result = db.lookup_part(query)
        print("\n" + result['message'])
        print("\n" + "-" * 50)
