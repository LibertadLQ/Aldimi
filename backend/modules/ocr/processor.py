"""
ALDIMI 2.0 — OCR Module Mejorado
Handles multiple hospital report formats with intelligent fallback
Compatible with notebook

Uso en notebook:
    from aldimi_ocr_module import EnhancedOCRProcessor
    processor = EnhancedOCRProcessor()
    result = processor.scan_report('/path/to/image.png')
"""

import re
import cv2
import numpy as np
import pytesseract
from PIL import Image
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging

# Minimal logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass
class PatientInfo:
    """Información del paciente extraída"""
    patient_id: Optional[str] = None
    name: Optional[str] = None
    age: Optional[int] = None
    date_collection: Optional[str] = None
    date_report: Optional[str] = None
    hospital: Optional[str] = None
    test_type: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LabValue:
    """Valor de laboratorio"""
    test_name: str
    value: float
    unit: str
    reference_range: Optional[str] = None
    status: Optional[str] = None  # normal, low, high, critical
    
    def to_dict(self) -> Dict:
        return asdict(self)


class EnhancedOCRProcessor:
    """Procesador OCR mejorado para informes médicos"""
    
    # Patrones específicos por hospital
    HOSPITAL_PATTERNS = {
        'manipal': {
            'name': r'Manipal\s+Hospitals',
            'patient_id': r'Patient\s+CIU\s*:?\s*([WV]\d+)',
            'date_pattern': r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\s+(\d{4})',
        },
        'srv': {
            'name': r'SRV\s+HOSPITALS',
            'patient_id': r'Patient\s+CIU\s*:?\s*([WV]\d+)',
            'date_pattern': r'(\d{1,2}-\d{1,2}-\d{4})',
        },
        'rg_stone': {
            'name': r'RG\s+STONE|R\.G\.\s+STONE',
            'patient_id': r'Patient\s+CIU\s*:?\s*([WV]\d+)',
        },
        'oscar': {
            'name': r'OSCAR\s+SUPER',
            'patient_id': r'Patient\s+CIU\s*:?\s*([WV]\d+)',
        }
    }
    
    # Unidades comunes en laboratorios
    COMMON_UNITS = {
        'mg/dl', 'mmol/L', 'g/dl', 'U/L', 'mL/min', '%', 'mg/L', 'pH',
        'fl', 'pg', 'g/L', 'IU/mL', 'ng/mL', 'µg/dL', 'mEq/L', 'cells/mm3',
        'g/dL', 'mcL', '/mm3', 'sec', 'Pa'
    }
    
    def __init__(self, use_preprocessing: bool = True):
        """
        Inicializar procesador

        Args:
            use_preprocessing: Si usar preprocesamiento de imagen (recomendado)
        """
        self.use_preprocessing = use_preprocessing
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Preprocesar imagen para mejorar OCR
        Aplica múltiples técnicas:
        - CLAHE (Contrast Limited Adaptive Histogram Equalization)
        - Bilateral filtering
        - Denoising
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")

        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Aplicar CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Bilateral filter (preserva bordes)
        bilateral = cv2.bilateralFilter(enhanced, 9, 75, 75)

        # Median filter para denoise
        denoised = cv2.medianBlur(bilateral, 3)

        return denoised
    
    def extract_text_robust(self, image_path: str) -> str:
        """
        Extraer texto usando Tesseract con preprocesamiento
        """
        try:
            if self.use_preprocessing:
                processed = self.preprocess_image(image_path)
                img_pil = Image.fromarray(processed)
            else:
                img_pil = Image.open(image_path)

            # Usar PSM 6 (bloque de texto uniforme) para tablas
            text = pytesseract.image_to_string(
                img_pil,
                lang='spa+eng',
                config='--psm 6 --oem 3'
            )
            return text
        except Exception as e:
            logger.warning(f"⚠️  OCR failed: {e}")
            return ""
    
    def detect_hospital(self, text: str) -> Optional[str]:
        """Detectar qué hospital es basado en el texto"""
        for hospital, patterns in self.HOSPITAL_PATTERNS.items():
            if re.search(patterns['name'], text, re.IGNORECASE):
                return hospital
        return None
    
    def extract_patient_info(self, text: str) -> PatientInfo:
        """
        Extraer información del paciente
        Usa patrones específicos según el hospital detectado
        """
        info = PatientInfo()
        
        # Detectar hospital
        hospital = self.detect_hospital(text)
        info.hospital = hospital or self.extract_hospital_generic(text)
        
        # Patient ID
        patterns_id = [
            r'CIU\s*:?\s*([WV]?\d{6,})',
            r'Patient.*?CIU\s*:?\s*([A-Z0-9]+)',
            r'Patient\s+(?:ID|CIU|Id)\s*:?\s*([WV]?\d+)',
        ]
        for pattern in patterns_id:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info.patient_id = match.group(1)
                break
        
        # Name (buscar patrones comunes)
        patterns_name = [
            # DNI: apellido y nombre después de fecha DOB (pos YYYY)
            r'pos\s+\d{2}/\d{2}/\d{4}\s*[^\n]*\n\s*[;>\|]?\s*([A-Z]{3,})[^\n]*\n\s*[;>\|]?\s*([A-Z]{3,})',
            # DNI: solo apellido después de fecha
            r'pos\s+\d{2}/\d{2}/\d{4}\s*[^\n]*\n\s*\|\s*([A-Z]{3,})\s*\(',
            # Patient Name en reportes médicos
            r'(?:Patient|Paciente)\s+Name\s*:?\s*([A-Z][A-Za-z\s]{2,40}?)(?:\n|Age|DOB)',
            # Dos palabras capitalizadas
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]
        for pattern in patterns_name:
            match = re.search(pattern, text)
            if match:
                # Si tiene 2 grupos (apellido + nombre)
                if match.lastindex and match.lastindex >= 2:
                    apellido = match.group(1).strip()
                    nombre = match.group(2).strip()
                    # Filtrar basura (palabras con caracteres extraños o muy cortas)
                    if len(apellido) >= 3 and len(nombre) >= 3 and apellido.isalpha() and nombre.isalpha():
                        name = f"{nombre} {apellido}"
                    else:
                        continue
                else:
                    name = match.group(1).strip()

                # Filtrar estados USA comunes
                if name.upper() not in ['WEST VIRGINIA', 'NEW YORK', 'CALIFORNIA', 'TEXAS', 'FLORIDA', 'GOVERNOR']:
                    if len(name) > 2:
                        info.name = name
                        break
        
        # Age
        match = re.search(r'Age\s*:?\s*(\d{1,3})', text, re.IGNORECASE)
        if match:
            try:
                info.age = int(match.group(1))
            except ValueError:
                pass
        
        # Date Collection
        patterns_date = [
            r'Collection\s+(?:on|Date)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(\d{2}-\d{2}-\d{4})\s+\d{2}:\d{2}',
        ]
        for pattern in patterns_date:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info.date_collection = match.group(1)
                break
        
        # Test Type
        test_types = ['SEROLOGY', 'BIOCHEMISTRY', 'HEMATOLOGY', 'PATHOLOGY', 'IMMUNOLOGY']
        for test in test_types:
            if re.search(test, text, re.IGNORECASE):
                info.test_type = test
                break
        
        return info
    
    def extract_hospital_generic(self, text: str) -> Optional[str]:
        """Extracción genérica de nombre de hospital"""
        hospitals = ['Manipal', 'SRV', 'RG Stone', 'Oscar', 'Fortis', 'Apollo']
        for h in hospitals:
            if re.search(h, text, re.IGNORECASE):
                return h
        return None
    
    def extract_lab_values(self, text: str) -> List[LabValue]:
        """
        Extraer valores de laboratorio del texto
        Busca patrones de la forma:
        TEST_NAME (método) VALOR UNIDAD [RANGO_REFERENCIA]
        Maneja variaciones: espacios, caracteres especiales (#, *), unidades mal formadas
        """
        values = []
        lines = text.split('\n')
        
        for line in lines:
            # Saltar líneas demasiado cortas
            stripped = line.strip()
            if len(stripped) < 10:
                continue
            
            # Saltar headers y secciones
            upper = stripped.upper()
            if any(h in upper for h in ['TEST', 'RESULT', 'INVESTIGATIONS', 
                                         'SPECIMEN', 'RENAL PANEL', 'BIOCHEMISTRY',
                                         'DISCLAIMER', 'REFERENCE', 'COLLECTION', 'REPORTING']):
                continue
            
            # Buscar patrón NEGATIVE/POSITIVE (para serology)
            text_match = re.search(r'(NEGATIVE|POSITIVE|REACTIVE|NON-REACTIVE)', stripped, re.IGNORECASE)
            if text_match and ':' in stripped:
                # Extraer nombre antes de ":"
                parts = stripped.split(':')
                if len(parts) >= 2:
                    test_name = parts[0].strip()
                    result_text = parts[1].strip().upper()

                    # Convertir a valor numérico (0 = negative, 1 = positive)
                    numeric_value = 1.0 if 'POSITIVE' in result_text or 'REACTIVE' in result_text else 0.0

                    if len(test_name) >= 3:
                        values.append(LabValue(
                            test_name=test_name,
                            value=numeric_value,
                            unit='qualitative',
                            reference_range=None,
                            status='negative' if numeric_value == 0 else 'positive'
                        ))
                        continue

            # Buscar patrón: línea con nombre + número + unidad
            # Patrón más permisivo para capturar variaciones
            num_match = re.search(r'(\d+\.?\d*)\s*[#*]?\s+([a-zA-Z/%\-]+)', stripped)

            if not num_match:
                continue
            
            try:
                value_str = num_match.group(1)
                unit_part = num_match.group(2).strip()
                
                # Extraer nombre (todo lo que va antes del número)
                value_pos = num_match.start(1)
                test_name = stripped[:value_pos].strip()
                
                # Limpiar nombre
                test_name = re.sub(r'[#*]+$', '', test_name).strip()
                test_name = re.sub(r'\s+$', '', test_name)
                
                # Validar nombre
                if not test_name or len(test_name) < 3 or len(test_name) > 100:
                    continue

                # Filtrar líneas que no son nombres de tests reales
                test_upper = test_name.upper()
                invalid_keywords = ['DATE', 'SRI NO', 'PATIENT', 'CIU', 'PATHOLOG', 'CONSULTANT',
                                   'SEROLOGICAL', 'IN ORDER TO', 'METHODS ARE', 'BASED METHODS',
                                   'ANTIBODIES BASED']
                if any(kw in test_upper for kw in invalid_keywords):
                    continue

                # Filtrar nombres demasiado cortos o que parecen código (NS-, ig, etc)
                if len(test_name) <= 3 and not test_name.isalpha():
                    continue

                # Remover caracteres de paciente si se mezcló
                if 'Patient' in test_name or 'CIU' in test_name:
                    test_name = re.sub(r'\s+Patient.*', '', test_name).strip()
                
                # Extraer unidad limpia (solo letras, /, %, -)
                unit = re.sub(r'[^a-zA-Z%/\-.]', '', unit_part)
                
                if not unit or len(unit) > 20:
                    continue
                
                # Validar que sea unidad médica común
                unit_lower = unit.lower()
                is_valid_unit = any(
                    u in unit_lower for u in 
                    ['mg', 'mmol', 'g', 'u/l', '/l', 'dl', 'ml', '%', 'ph', 'fl', 'pg', 'sec', 'pa', 'iu', '/']
                )
                
                if not is_valid_unit:
                    continue
                
                try:
                    value = float(value_str)
                except ValueError:
                    continue
                
                # Extraer rango de referencia
                ref_match = re.search(r'\[([\d\.\-\s<>]+)\]', line)
                reference = ref_match.group(1).strip() if ref_match else None
                
                # Agregar valor extraído
                values.append(LabValue(
                    test_name=test_name,
                    value=value,
                    unit=unit,
                    reference_range=reference
                ))
            
            except (ValueError, AttributeError, IndexError):
                continue
        
        return values
    
    def scan_report(self, image_path: str) -> Dict[str, Any]:
        """
        Escanear un informe médico completo
        
        Retorna:
        {
            'status': 'success' | 'partial' | 'error',
            'file': nombre del archivo,
            'patient': {patient info dict},
            'lab_values': [list of lab values],
            'text_length': caracteres extraídos,
            'hospital': hospital detectado
        }
        """
        try:
            image_path = str(image_path)
            
            # Extraer texto
            text = self.extract_text_robust(image_path)
            
            if not text or len(text.strip()) < 50:
                return {
                    'status': 'error',
                    'file': Path(image_path).name,
                    'error': 'OCR extraction too short or empty'
                }
            
            # Extraer información estructurada
            patient = self.extract_patient_info(text)
            lab_values = self.extract_lab_values(text)
            
            # Determinar status
            has_patient_data = any([
                patient.patient_id,
                patient.name,
                patient.date_collection
            ])
            has_lab_data = len(lab_values) > 0
            
            if has_patient_data and has_lab_data:
                status = 'success'
            elif has_patient_data or has_lab_data:
                status = 'partial'
            else:
                status = 'error'
            
            return {
                'status': status,
                'file': Path(image_path).name,
                'patient': patient.to_dict(),
                'lab_values': [v.to_dict() for v in lab_values],
                'text_length': len(text),
                'hospital': patient.hospital
            }
        
        except Exception as e:
            logger.error(f"Error scanning {image_path}: {e}")
            return {
                'status': 'error',
                'file': Path(image_path).name,
                'error': str(e)
            }
    
    def batch_scan(self, directory: str) -> List[Dict[str, Any]]:
        """
        Escanear múltiples reportes de un directorio
        """
        directory = Path(directory)
        image_files = list(directory.glob('*.png')) + list(directory.glob('*.jpg'))
        
        results = []
        for i, img_path in enumerate(image_files, 1):
            logger.info(f"[{i}/{len(image_files)}] Scanning {img_path.name}...")
            result = self.scan_report(str(img_path))
            results.append(result)
        
        return results


def print_results_summary(results: List[Dict[str, Any]]):
    """Imprimir resumen de resultados"""
    print("\n" + "="*80)
    print("📋 OCR SCAN RESULTS SUMMARY")
    print("="*80)
    
    for result in results:
        status_icon = {'success': '✅', 'partial': '⚠️', 'error': '❌'}.get(result['status'], '?')
        
        print(f"\n{status_icon} {result['file']}")
        print(f"   Status: {result['status']}")
        
        if result['status'] != 'error':
            patient = result.get('patient', {})
            if patient:
                print(f"   Hospital: {patient.get('hospital', 'Unknown')}")
                if patient.get('patient_id'):
                    print(f"   Patient ID: {patient['patient_id']}")
                if patient.get('date_collection'):
                    print(f"   Collection: {patient['date_collection']}")
            
            lab_values = result.get('lab_values', [])
            print(f"   Lab Values Found: {len(lab_values)}")
            if lab_values:
                for val in lab_values[:3]:
                    print(f"      • {val['test_name']}: {val['value']} {val['unit']}")
                if len(lab_values) > 3:
                    print(f"      ... and {len(lab_values) - 3} more")
        else:
            print(f"   Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "="*80)
    successful = sum(1 for r in results if r['status'] in ['success', 'partial'])
    print(f"Summary: {successful}/{len(results)} reports successfully scanned")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Test the module
    import sys
    
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = '/mnt/user-data/uploads'
    
    processor = EnhancedOCRProcessor(use_preprocessing=True)
    
    if Path(target).is_dir():
        results = processor.batch_scan(target)
    else:
        results = [processor.scan_report(target)]
    
    print_results_summary(results)
