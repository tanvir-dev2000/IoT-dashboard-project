# backend/timezone_utils.py
import datetime
import pytz
import platform
import os


def get_bangladesh_time():
    """Get current time in Bangladesh timezone - works on all platforms"""
    utc_now = datetime.datetime.utcnow()
    utc_tz = pytz.timezone('UTC')
    bd_tz = pytz.timezone('Asia/Dhaka')

    # Make UTC time timezone-aware
    utc_aware = utc_tz.localize(utc_now)

    # Convert to Bangladesh time
    bd_time = utc_aware.astimezone(bd_tz)

    return bd_time


def get_bangladesh_time_str(format_str='%I:%M:%S %p'):
    """Get Bangladesh time as formatted string"""
    return get_bangladesh_time().strftime(format_str)


def get_bangladesh_date_str(format_str='%d/%m/%Y'):
    """Get Bangladesh date as formatted string"""
    return get_bangladesh_time().strftime(format_str)


def setup_timezone():
    """Setup timezone - cross-platform compatible"""
    # Set environment variable for Unix systems
    os.environ['TZ'] = 'Asia/Dhaka'

    # Only use tzset on Unix-like systems
    if platform.system() != 'Windows':
        import time
        time.tzset()
        print("Timezone set to Asia/Dhaka using tzset()")
    else:
        print("Windows detected - using pytz for timezone handling")


def get_current_time_for_platform():
    """
    Get current time using the best method for the platform
    Returns format: 'YYYY-MM-DD HH:MM:SS' (24-hour format for data_processor)
    """
    if platform.system() != 'Windows' and os.environ.get('TZ') == 'Asia/Dhaka':
        # On Unix with timezone set, use system time in 24-hour format
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    else:
        # Fallback to pytz conversion (Windows or if tzset failed)
        return get_bangladesh_time().strftime('%Y-%m-%d %H:%M:%S')


def get_current_time_12hr_for_display():
    """
    Get current time in 12-hour format for display purposes
    Returns format: 'HH:MM:SS AM/PM'
    """
    if platform.system() != 'Windows' and os.environ.get('TZ') == 'Asia/Dhaka':
        # On Unix with timezone set, use system time
        return datetime.datetime.now().strftime('%I:%M:%S %p')
    else:
        # Fallback to pytz conversion (Windows or if tzset failed)
        return get_bangladesh_time_str()
