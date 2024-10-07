import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Slack Webhook URL from your environment variables
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_message(message):
    payload = {
        "text": message
    }
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    if response.status_code != 200:
        print(f"Failed to send message to Slack: {response.status_code}, {response.text}")

# Function to call the API and retrieve data
def fetch_energy_prices(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()  # Assuming API returns JSON response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

# Function to combine time slots into multi-hour slots where total_price is under 2
def combine_time_slots(energy_prices):
    filtered_slots = []
    current_slot = None

    # Get the current datetime to filter out past time slots
    now = datetime.now()

    for slot in energy_prices:
        time_start = datetime.strptime(slot['time_start'], "%a, %d %b %Y %H:%M:%S %Z")
        time_end = datetime.strptime(slot['time_end'], "%a, %d %b %Y %H:%M:%S %Z")

        # Skip past time slots
        if time_end <= now:
            continue

        price = float(slot['total_price'])
        if price >= 2:
            # Close the current slot if total_price >= 2 and start fresh
            if current_slot:
                filtered_slots.append(current_slot)
                current_slot = None
            continue

        if current_slot:
            # Check if this slot is consecutive with the last one
            if time_start == current_slot['time_end']:
                # Extend the current slot and update prices
                current_slot['time_end'] = time_end
                current_slot['total_price'] += price
                current_slot['hourly_prices'].append({'time_start': time_start, 'time_end': time_end, 'price': price})
            else:
                # If not consecutive, save the current slot and start a new one
                filtered_slots.append(current_slot)
                current_slot = {
                    'time_start': time_start,
                    'time_end': time_end,
                    'total_price': price,
                    'hourly_prices': [{'time_start': time_start, 'time_end': time_end, 'price': price}]
                }
        else:
            # Start a new slot
            current_slot = {
                'time_start': time_start,
                'time_end': time_end,
                'total_price': price,
                'hourly_prices': [{'time_start': time_start, 'time_end': time_end, 'price': price}]
            }

    # Append the last slot if it's still open
    if current_slot:
        filtered_slots.append(current_slot)

    return filtered_slots

# Function to find the lowest 25% of multi-hour time slots
def find_lowest_25_percent(slots):
    # Sort by total price
    slots.sort(key=lambda x: x['total_price'])
    
    # Calculate the number of slots in the lowest 25%
    n = len(slots)
    count = max(1, n // 4)  # Ensure at least 1 slot is selected, even for small sets
    
    return slots[:count]

# Display the result with price for each hour in the slot
def display_slots(slots):
    # Construct the message for Slack
    if not slots:
        message = "No low-price time slots found."
        print(message)  # Print the message if no slots are found
    else:
        message = f"Found {len(slots)} low-price time slot(s):\n"
        print(f"Found {len(slots)} low-price time slot(s):")  # Print the number of slots
        
        for slot in slots:
            time_start_str = slot['time_start'].strftime("%Y-%m-%d %H:%M")
            time_end_str = slot['time_end'].strftime("%Y-%m-%d %H:%M")
            message += f"\nFrom {time_start_str} to {time_end_str}:\n"
            print(f"\nFrom {time_start_str} to {time_end_str}:")  # Print the time range of the slot

            # Append and print the price for each hour within the slot
            for hourly in slot['hourly_prices']:
                hourly_start = hourly['time_start'].strftime("%Y-%m-%d %H:%M")
                hourly_end = hourly['time_end'].strftime("%Y-%m-%d %H:%M")
                hourly_price = f"{hourly['price']:.2f} DKK"
                
                message += f"  {hourly_start} - {hourly_end}: {hourly_price}\n"
                print(f"  {hourly_start} - {hourly_end}: {hourly_price}")  # Print each hourly price

    # Call the function to send the message to Slack
    send_slack_message(message)

# Main function to execute the script
if __name__ == "__main__":
    date = datetime.now().strftime("%Y-%m-%d")

    api_url = f"https://elpriser.repono.dk/api/energy-prices?start_date={date}"  # Replace with actual API URL
    
    # Fetch energy prices data from the API
    energy_prices = fetch_energy_prices(api_url)
    
    # Combine consecutive time slots with total_price < 2
    multi_hour_slots = combine_time_slots(energy_prices)
    
    # Find the lowest 25% of the combined multi-hour slots
    lowest_25_percent_slots = find_lowest_25_percent(multi_hour_slots)
    
    # Display the results
    display_slots(lowest_25_percent_slots)