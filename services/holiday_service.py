from datetime import date

def get_algerian_holidays(year):
    """
    Returns a list of fixed Algerian national holidays for a given year.
    Note: Religious holidays (Eid, Mawlid) are variable and ideally 
    should be managed via a config or database for a real production system.
    For now, we'll handle fixed dates and a simple placeholder logic for variable ones.
    """
    fixed_holidays = {
        (1, 1): "Jour de l'an",
        (1, 12): "Yennayer (Nouvel an Berbère)",
        (5, 1): "Fête du Travail",      
        (11, 1): "Révolution du 1er Novembre",
    }
    
    holiday_dates = [date(year, month, day) for (month, day) in fixed_holidays.keys()]
    return holiday_dates

def is_holiday_or_friday(d):
    """
    Checks if a given date is a Friday or an Algerian national holiday.
    """
    # Friday is the official weekend in Algeria
    if d.weekday() == 4:
        return True
    
    holidays = get_algerian_holidays(d.year)
    if d in holidays:
        return True
        
    return False
