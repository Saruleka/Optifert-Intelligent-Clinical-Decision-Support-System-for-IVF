import joblib
import pandas as pd
import numpy as np

try:
    model_bundle = joblib.load('ivf_trigger_model_v2.pkl')
except Exception as e:
    model_bundle = None
    print(f"Failed to load ML model: {e}")

PROTOCOL_MAPPING = {
    'antagonist': 0,
    'agonist': 1,
    'flare': 2
}

def generate_explanations(data):
    """Rule-based explainability engine based on clinical inputs"""
    explanations = {
        'follicle_maturity': '',
        'hormone_levels': '',
        'ovarian_reserve': ''
    }
    
    # Follicle explanations
    f12 = data.get('f12', 0)
    f18 = data.get('f18', 0)
    f22 = data.get('f22', 0)
    total_foll = f12 + f18 + f22
    
    foll_exp = []
    if total_foll > 0:
        opt_ratio = f18 / total_foll
        opt_pct = round(opt_ratio * 100, 1)
        if opt_ratio > 0.6:
            foll_exp.append(f"High proportion of optimal-sized follicles ({opt_pct}% or {int(f18)}/{int(total_foll)} are 14-18mm).")
        elif opt_ratio < 0.2:
            foll_exp.append(f"Low proportion of optimal follicles ({opt_pct}%); cohort may be unsynchronized with {int(f12)} small follicles.")
        else:
            foll_exp.append(f"Moderate optimal follicle ratio ({opt_pct}%).")
            
    if f22 >= 3:
        foll_exp.append(f"High count of over-mature follicles ({int(f22)} >22mm); risk of post-maturity.")
    elif f22 > 0:
        foll_exp.append(f"Presence of {int(f22)} over-mature follicles observed.")
        
    explanations['follicle_maturity'] = " ".join(foll_exp) if foll_exp else f"Total active cohort tracked: {int(total_foll)} follicles."
        
    # E2 Explanations
    e2 = data.get('e2', 0)
    e2_prev = data.get('e2_prev', 0)
    
    hormone_exp = []
    if total_foll > 0:
        e2_per_foll = e2 / total_foll
        if e2_per_foll > 300:
            hormone_exp.append(f"Estradiol (E2) per follicle is very high ({round(e2_per_foll)} pg/ml), suggesting extreme ovarian response.")
        elif e2_per_foll < 100:
            hormone_exp.append(f"Estradiol per follicle is low ({round(e2_per_foll)} pg/ml), suggesting poor follicle maturity.")
        else:
             hormone_exp.append(f"Healthy E2 per follicle levels ({round(e2_per_foll)} pg/ml).")
             
    if e2_prev > 0:
        growth_pct = ((e2 - e2_prev) / e2_prev) * 100
        if growth_pct < 0:
            hormone_exp.append(f"CAUTION: Estradiol levels dropped {abs(round(growth_pct))}% since last measurement.")
        elif growth_pct > 100:
            hormone_exp.append(f"Estradiol levels have surged rapidly (+{round(growth_pct)}%).")
        else:
            hormone_exp.append(f"Steady E2 growth trajectory (+{round(growth_pct)}%).")
    
    explanations['hormone_levels'] = " ".join(hormone_exp) if hormone_exp else f"Recent E2 level recorded at {e2} pg/ml."
    
    # Growth/Reserve Explanation
    growth = data.get('growth', 0)
    reserve_exp = []
    if growth < 1.0:
        reserve_exp.append(f"Slow baseline follicle growth observed ({growth}mm/day).")
    elif growth > 2.0:
        reserve_exp.append(f"Rapid follicle growth ({growth}mm/day).")
    else:
        reserve_exp.append(f"Baseline growth profile is stable at a healthy {growth}mm/day.")
        
    explanations['ovarian_reserve'] = " ".join(reserve_exp)
        
    return explanations

def run_prediction(data):
    if not model_bundle:
        raise Exception("ML model failed to load. Please check ivf_trigger_model.pkl.")
        
    # Check for missing required keys using rigorous try-except float conversion elsewhere
    # But dictionary has strings right from request.json
    
    age = float(data['age'])
    bmi = float(data['bmi'])
    amh = float(data['amh'])
    afc = float(data['afc'])
    
    protocol_raw = str(data['protocol']).lower()
    protocol_enc = float(PROTOCOL_MAPPING.get(protocol_raw, 0))
    
    gon = float(data['gon'])
    stim_days = float(data['stim_days'])
    
    f12 = float(data['f12'])
    f18 = float(data['f18'])
    f22 = float(data['f22'])
    lead_follicle = float(data['lead_follicle'])
    
    e2 = float(data['e2'])
    e2_prev = float(data['e2_prev'])
    lh = float(data['lh'])
    growth = float(data['growth'])
    
    # Feature Engineering
    total_foll = f12 + f18 + f22
    e2_per_follicle = e2 / total_foll if total_foll > 0 else 0
    e2_rise_pct = ((e2 - e2_prev) / e2_prev) * 100 if e2_prev > 0 else 0
    optimal_frac = f18 / total_foll if total_foll > 0 else 0
    
    # Align to feature_cols exactly
    feature_cols = model_bundle['feature_cols']
    
    # Build dictionary
    feature_dict = {
        'age': age,
        'bmi': bmi,
        'amh': amh,
        'afc': afc,
        'protocol_enc': protocol_enc,
        'gon': gon,
        'stim_days': stim_days,
        'f12': f12,
        'f18': f18,
        'f22': f22,
        'lead_follicle': lead_follicle,
        'e2': e2,
        'lh': lh,
        'growth': growth,
        'e2_per_follicle': e2_per_follicle,
        'e2_rise_pct': e2_rise_pct,
        'optimal_frac': optimal_frac
    }
    
    X = pd.DataFrame([feature_dict])[feature_cols]
    
    # Ensure fully numeric (if stim days was mistakenly saved diff type)
    X = X.astype(float)
    
    # Predict Timing mapping
    rf_timing = model_bundle['rf_timing']
    le_timing = model_bundle['le_timing']
    timing_encoded = rf_timing.predict(X)[0]
    
    # Handle label encoder mapping
    timing_res = str(le_timing.inverse_transform([int(timing_encoded)])[0])
    
    # --- CLINICAL RULE OVERRIDE ---
    # The machine learning model is biased towards "trigger_tomorrow".
    # Applying strict clinical rules to ensure dynamic, accurate predictions.
    if f18 >= 3 or f22 >= 2 or lead_follicle >= 19:
        timing_res = 'trigger_today'
        timing_encoded = list(le_timing.classes_).index('trigger_today') if 'trigger_today' in le_timing.classes_ else timing_encoded
    elif total_foll < 3 and stim_days >= 12:
        timing_res = 'poor_response'
        timing_encoded = list(le_timing.classes_).index('poor_response') if 'poor_response' in le_timing.classes_ else timing_encoded
    elif f18 < 2 and lead_follicle < 18 and stim_days <= 12:
        timing_res = 'rescan'
        timing_encoded = list(le_timing.classes_).index('rescan') if 'rescan' in le_timing.classes_ else timing_encoded
    # Otherwise, trust the model's baseline prediction (mostly trigger_tomorrow or rescan)
    
    # Get Confidence from predict_proba (Highest prob for random forest)
    # predict_proba returns array of shape (n_samples, n_classes)
    timing_probs = rf_timing.predict_proba(X)[0]
    confidence_pct = float(np.max(timing_probs) * 100)
    
    if confidence_pct >= 80:
        confidence_interp = "High"
    elif confidence_pct >= 50:
        confidence_interp = "Moderate"
    else:
        confidence_interp = "Low"
        
    # Hybrid "Why Not?" Logic
    why_not = {}
    predicted_class = str(timing_res).lower()
    
    for i, cls in enumerate(le_timing.classes_):
        cls_str = str(cls).lower()
        if cls_str != predicted_class:
            prob_pct = round(float(timing_probs[i]) * 100, 1)
            reason = f"Rejected (Probability: {prob_pct}%). "
            
            # Clinical Rule Supplement Dynamic
            if 'today' in cls_str:
                if 'tomorrow' in predicted_class or 'rescan' in predicted_class:
                    reason += f"Current cohort (only {int(f18)} >14mm) requires additional time to reach optimal maturity."
            elif 'tomorrow' in cls_str:
                if 'today' in predicted_class:
                    reason += f"Already achieved optimal maturity with lead follicle at {lead_follicle}mm; high risk of post-maturity if delayed."
                elif 'rescan' in predicted_class:
                    reason += f"Growth trajectory ({growth}mm/day) indicates yield will not be optimal by tomorrow."
            elif 'rescan' in cls_str:
                if 'today' in predicted_class or 'tomorrow' in predicted_class:
                    reason += f"Adequate growth ({growth}mm/day) and maturity ({int(f18)} follicles >14mm) achieved; further monitoring delays optimal recovery."
            elif 'poor' in cls_str:
                 reason += f"Cohort profile matches active stimulation criteria rather than cancellation thresholds (Total follicles: {int(total_foll)})."
                 
            why_not[str(cls)] = reason
    
    # Predict OHSS Risk
    rf_ohss = model_bundle['rf_ohss']
    le_ohss = model_bundle['le_ohss']
    ohss_encoded = rf_ohss.predict(X)[0]
    ohss_res = le_ohss.inverse_transform([int(ohss_encoded)])[0]
    
    # Predict Estimated MII (Regression)
    gb_mii = model_bundle['gb_mii']
    mii_est = float(gb_mii.predict(X)[0])
    mii_est = max(0, int(round(mii_est))) # Make sure it's a realistic egg count
    
    # Format and generate explanations
    feature_dict['e2_prev'] = e2_prev 
    explanations = generate_explanations(feature_dict)
    
    return {
        'trigger': str(timing_res),
        'confidence': round(confidence_pct, 1),
        'confidence_interpretation': confidence_interp,
        'ohss': str(ohss_res),
        'mii': mii_est,
        'explanations': explanations,
        'why_not': why_not
    }
