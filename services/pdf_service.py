from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import os
from services.holiday_service import is_holiday_or_friday
from database import firestore_db as db

class RosterPDF(FPDF):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._custom_font = False
        win_regular = r"C:\Windows\Fonts\arial.ttf"
        win_bold = r"C:\Windows\Fonts\arialbd.ttf"
        linux_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        linux_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        regular = win_regular if os.path.isfile(win_regular) else linux_regular
        bold = win_bold if os.path.isfile(win_bold) else linux_bold

        if os.path.isfile(regular):
            self.add_font("Arial", "", regular)
            self._custom_font = True
        if os.path.isfile(bold):
            self.add_font("Arial", "B", bold)
            self._custom_font = True

        if self._custom_font:
            self.set_font("Arial", size=9)
        else:
            self.set_font("Helvetica", size=9)

    @property
    def fn(self):
        return "Arial" if self._custom_font else "Helvetica"

    def main_header(self, wilaya_fr, title_data):
        # 1. Republic and Ministry (Centered)
        # Unified Font and Spacing as requested
        self.set_y(2)
        self.set_font(self.fn, "B", 10)
        self.cell(0, 5, "République Algérienne Démocratique et Populaire", ln=True, align="C")
        self.cell(0, 5, fix_text("Ministère de la Santé"), ln=True, align="C")
        self.cell(0, 5, f"Direction de la Santé et de la Population - Wilaya de {wilaya_fr}", ln=True, align="C")
        
        self.ln(2)
        
        # 3. Stylish Title Bar (Combined)
        self.set_fill_color(255, 255, 255) # White background
        self.set_text_color(0, 0, 0) # Black text
        self.set_font(self.fn, "B", 8)
        
        page_width = self.w - 10
        
        # Calculate roughly equal widths or weighted widths
        # Total ~ 200mm
        # Title: 70mm, Daira: 50mm, Nuit: 30mm, Vendredi: 50mm
        w1 = 70
        w2 = 50
        w3 = 30
        w4 = page_width - w1 - w2 - w3
        
        self.cell(w1, 8, f"TABLEAU DE GARDE - {title_data['month'].upper()} {title_data['year']}", border="B", align="L", fill=True)
        self.cell(w2, 8, f"Daira: {title_data['daira'].upper()}", border="B", align="L", fill=True)
        self.cell(w3, 8, "Nuit (19h-08h)", border="B", align="C", fill=True)
        self.cell(w4, 8, "Vendredi/Férié: (08h-19h)", border="B", align="R", ln=True, fill=True)
        self.ln(1)

def fix_text(text):
    if not text: return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def get_text_lines(pdf, text, width, font_style, font_size):
    """
    Calculate how many lines a text will occupy in a specific width.
    """
    if not text:
        return 0
    pdf.set_font(pdf.fn, font_style, font_size)
    text_w = pdf.get_string_width(text)
    if text_w == 0:
        return 0
        
    # Approximate character width is tough, simpler approach:
    # Use fpdf's multi_cell split/wrap logic? 
    # Or simple estimation: width available vs text width.
    # Text wrapping isn't just pure division (word boundaries), so we add a buffer.
    # For a robust solution without modifying FPDF internals, we can trust the division for now with a slight buffer.
    import math
    return math.ceil(text_w / (width - 1)) # -1 for safety margin

def generate_roster_pdf(year, month, daira, table_data, municipalities, pharmacist_dict=None):
    return generate_batch_roster_pdf(year, month, [(daira, table_data, municipalities)], pharmacist_dict)

def generate_batch_roster_pdf(year, month, dairas_data, pharmacist_dict=None):
    """
    dairas_data: list of tuples (daira_obj, table_data, municipalities_list)
    """
    pdf = RosterPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(5, 2, 5)
    
    month_names_fr = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]
    
    for daira, table_data, municipalities in dairas_data:
        pdf.add_page()
        
        title_data = {
            "month": month_names_fr[int(month)],
            "year": year,
            "daira": daira.name_fr
        }
        
        pdf.main_header("Djelfa", title_data)
        
        # Table Structure Setup
        page_width = pdf.w - 10
        date_w = 8
        day_name_w = 18
        available_w = page_width - date_w - day_name_w
        num_muni = min(len(municipalities), 5)
        muni_w = available_w / num_muni if num_muni > 0 else available_w
        
        # Table Header
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font(pdf.fn, "B", 8)
        h = 8
        
        pdf.cell(date_w, h, "Date", border=1, align="C", fill=True)
        pdf.cell(day_name_w, h, "Jour", border=1, align="C", fill=True)
        
        for muni in municipalities[:num_muni]:
            pdf.cell(muni_w, h, muni.name_fr.upper(), border=1, align="C", fill=True)
        pdf.ln()

        # Table Body
        pdf.set_font(pdf.fn, "", 7)
        
        for i, (date_obj, day_name, day_name_ar, duties) in enumerate(table_data):
            is_holiday = is_holiday_or_friday(date_obj)
            
            # Calculate required height for this row based on content
            max_lines = 1
            row_content = [] # Store pre-processed content to avoid re-calculating
            
            for j in range(num_muni):
                muni_duties = duties[j] if j < len(duties) else []
                night_duty = next((d for d in muni_duties if d.shift_type == 'NIGHT'), None)
                day_duty = next((d for d in muni_duties if d.shift_type == 'HOLIDAY_DAY'), None)
                if pharmacist_dict:
                    night_ph = pharmacist_dict.get(night_duty.pharmacist_id) if night_duty else None
                    day_ph = pharmacist_dict.get(day_duty.pharmacist_id) if day_duty else None
                else:
                    night_ph = db.get_pharmacist(night_duty.pharmacist_id) if night_duty else None
                    day_ph = db.get_pharmacist(day_duty.pharmacist_id) if day_duty else None
                
                day_text = ""
                night_text = ""
                day_lines = 0
                night_lines = 0
                
                if day_ph:
                    address_str = f" ({day_ph.address_fr})" if day_ph.address_fr else ""
                    day_text = f"J: {day_ph.name_fr}{address_str}"
                    day_lines = get_text_lines(pdf, day_text, muni_w - 2, "B", 6)
                
                if night_ph:
                    address_str = f" ({night_ph.address_fr})" if night_ph.address_fr else ""
                    night_text = f"N: {night_ph.name_fr}{address_str}"
                    night_lines = get_text_lines(pdf, night_text, muni_w - 2, "", 6)
                
                total_lines = day_lines + night_lines
                if day_ph and night_ph:
                     total_lines += 0.5 # Add small gap between them
                
                row_content.append({
                    "day_text": day_text, "night_text": night_text,
                    "day_lines": day_lines, "night_lines": night_lines
                })
                
                if total_lines > max_lines:
                    max_lines = total_lines

            # Calculate dynamic row height
            # Base height (6mm or 10mm) vs Content height
            # Line height approx 2.5mm for 6pt font
            content_height = 1 + (max_lines * 2.5) + 1 
            min_h = 10 if is_holiday else 6
            current_row_h = max(min_h, content_height)
            
            # Draw Background and Grid
            if is_holiday:
                pdf.set_fill_color(224, 224, 224)
            else:
                pdf.set_fill_color(255, 255, 255)
                
            fill = True
            pdf.set_font(pdf.fn, "B" if is_holiday else "", 7)
            
            # Check for page break
            if pdf.get_y() + current_row_h > 295:
                pdf.add_page()
                pdf.main_header("Djelfa", title_data)
                # Redraw Header
                pdf.set_fill_color(241, 245, 249)
                pdf.set_font(pdf.fn, "B", 8)
                pdf.cell(date_w, h, "Date", border=1, align="C", fill=True)
                pdf.cell(day_name_w, h, "Jour", border=1, align="C", fill=True)
                for muni in municipalities[:num_muni]:
                    pdf.cell(muni_w, h, muni.name_fr.upper(), border=1, align="C", fill=True)
                pdf.ln()
                pdf.set_font(pdf.fn, "", 7)
                # Reset fill
                if is_holiday:
                    pdf.set_fill_color(224, 224, 224)
                else:
                    pdf.set_fill_color(255, 255, 255)

            # Draw Date and Day cells (Vertically centered ideally, but top align is safer for now)
            # Actually, let's just fill the background first
            x_start = pdf.get_x()
            y_start = pdf.get_y()
            
            # Draw row background rects first for all columns ensures clean look
            # Date Col
            pdf.rect(x_start, y_start, date_w, current_row_h, style="FD")
            pdf.set_xy(x_start + date_w, y_start)
            # Day Col
            pdf.rect(pdf.get_x(), y_start, day_name_w, current_row_h, style="FD")
            pdf.set_xy(x_start + date_w + day_name_w, y_start)
            
            # Muni Cols
            for _ in range(num_muni):
                pdf.rect(pdf.get_x(), y_start, muni_w, current_row_h, style="FD")
                pdf.set_x(pdf.get_x() + muni_w)
                
            # Now Draw Text over background
            pdf.set_xy(x_start, y_start)
            
            # Date Content
            pdf.set_text_color(0, 0, 0)
            # Vertically center date/day
            text_y_offset = (current_row_h - 3) / 2
            
            pdf.set_xy(x_start, y_start + text_y_offset)
            pdf.cell(date_w, 3, date_obj.strftime('%d'), border=0, align="C")
            
            pdf.set_xy(x_start + date_w, y_start + text_y_offset)
            pdf.cell(day_name_w, 3, day_name, border=0, align="L")
            
            curr_x = x_start + date_w + day_name_w
            
            for j in range(num_muni):
                content = row_content[j]
                pdf.set_xy(curr_x, y_start)
                
                # Internal cell padding
                cell_padding = 1
                
                if content["day_text"]:
                    pdf.set_font(pdf.fn, "B", 6)
                    pdf.set_text_color(185, 28, 28)
                    pdf.set_xy(curr_x + 1, y_start + cell_padding)
                    pdf.multi_cell(muni_w - 2, 2.5, content["day_text"], align="L")
                
                if content["night_text"]:
                    pdf.set_font(pdf.fn, "", 6)
                    pdf.set_text_color(0, 0, 0)
                    
                    # Calculate Y position for night text
                    night_y = y_start + cell_padding
                    if content["day_text"]:
                        # If day text exists, night text goes after it
                        night_y += (content["day_lines"] * 2.5) + 1 # +1 gap
                    else:
                        # If no day text, vertically center night text? 
                        # Or just top align for consistency? Let's top align but respect min height centering if solitary
                        if current_row_h <= 10: # If it's a short row
                             night_y = y_start + (current_row_h - (content["night_lines"]*2.5))/2

                    pdf.set_xy(curr_x + 1, night_y)
                    pdf.multi_cell(muni_w - 2, 2.5, content["night_text"], align="L")
                
                curr_x += muni_w

            # Move to next line position
            pdf.set_xy(x_start, y_start + current_row_h) # Ensure we move down by the FULL height

    return pdf.output()
