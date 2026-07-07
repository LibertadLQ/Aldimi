#!/usr/bin/env python3
"""
ALDIMI 2.0 — Enhanced OCR Medical Report Scanner
Maneja múltiples formatos de hospitales con fallback automático
"""

import os
import re
import json
import cv2
import numpy as np
import pytesseract
import easyocr
from PIL import Image
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedOCRScanner:
    """Scanner OCR mejorado con múltiples técnicas de procesamiento"""
    
    def __init__(self):
        """Inicializar scanner con herramientas OCR"""
        self.reader = None
        try:
            # Inicializar EasyOCR como fallback (más robusto para imágenes de baja calidad)
            self.reader = easyocr.Reader(['es', 'en'], gpu=False)
            logger.info("✅ EasyOCR inicializado")
        except Exception as e:
            logger.warning(f"⚠️  EasyOCR falló: {e}")
    
    def preprocess_image(self, image_path: str, technique: str = 'standard') -> np.ndarray:
        """
        Preprocesar imagen para mejorar OCR
        
        Técnicas:
        - standard: contraste + escala de grises
        - aggressive: + bilateral filter + umbralización
        - clahe: Contrast Limited Adaptive Histogram Equalization
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"No se puede cargar imagen: {image_path}")
        
        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if technique == 'standard':
            # Mejorar contraste
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return enhanced
        
        elif technique == 'aggressive':
            # Aplicar bilateral filter (reduce ruido pero preserva bordes)
            bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
            # Threshold adaptativo
            thresh = cv2.adaptiveThreshold(bilateral, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 11, 2)
            return thresh
        
        elif technique == 'clahe':
            # CLAHE para mejor contraste
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            # Denoising
            denoised = cv2.medianBlur(enhanced, 3)
            return denoised
        
        return gray
    
    def extract_with_tesseract(self, image_path: str, preprocessed: bool = True) -> str:
        """Extraer texto con Tesseract + preprocesamiento"""
        try:
            if preprocessed:
                # Probar múltiples técnicas de preprocesamiento
                texts = []
                for tech in ['standard', 'aggressive', 'clahe']:
                    processed = self.preprocess_image(image_path, technique=tech)
                    # Convertir ndarray a PIL Image
                    pil_img = Image.fromarray(processed)
                    text = pytesseract.image_to_string(
                        pil_img, 
                        lang='spa+eng',
                        config='--psm 6 --oem 3'
                    )
                    texts.append(text)
                
                # Retornar el más largo (probablemente el mejor)
                return max(texts, key=len)
            else:
                img = Image.open(image_path)
                return pytesseract.image_to_string(img, lang='spa+eng', config='--psm 6 --oem 3')
        except Exception as e:
            logger.warning(f"Tesseract falló: {e}")
            return ""
    
    def extract_with_easyocr(self, image_path: str) -> str:
        """Extraer texto con EasyOCR (más robusto para baja calidad)"""
        try:
            if self.reader is None:
                return ""
            
            results = self.reader.readtext(image_path)
            text = '\n'.join([result[1] for result in results])
            return text
        except Exception as e:
            logger.warning(f"EasyOCR falló: {e}")
            return ""
    
    def extract_text_smart(self, image_path: str) -> Tuple[str, str]:
        """
        Extraer texto con fallback inteligente
        Retorna (texto, método_usado)
        """
        logger.info(f"🔍 Escaneando: {Path(image_path).name}")
        
        # Intentar Tesseract primero
        text = self.extract_with_tesseract(image_path, preprocessed=True)
        
        if len(text.strip()) > 100:
            logger.info(f"✅ Tesseract éxito ({len(text)} caracteres)")
            return text, "tesseract"
        
        # Fallback a EasyOCR
        logger.info("⚠️  Tesseract insuficiente, intentando EasyOCR...")
        text = self.extract_with_easyocr(image_path)
        
        if len(text.strip()) > 100:
            logger.info(f"✅ EasyOCR éxito ({len(text)} caracteres)")
            return text, "easyocr"
        
        logger.warning("❌ Ambos métodos fallaron")
        return text, "fallback"
    
    def extract_patient_data(self, text: str) -> Dict:
        """
        Extraer datos del paciente del texto OCR
        Busca patrones comunes en informes médicos
        """
        data = {}
        
        # Patrones para buscar (grupo de captura opcional)
        patterns = {
            'patient_id': [
                (r'CIU\s*:?\s*([WV]?\d+)', 1),
                (r'Patient\s+CIU\s*:?\s*([WV]?\d+)', 1),
                (r'Patient.*?CIU\s*:?\s*([A-Z0-9]+)', 1),
            ],
            'name': [
                (r'Patient\s+Name\s*:?\s*([A-Z][A-Za-z\s]+?)(?:\n|Age|Req)', 1),
                (r'(?:NIKHIL|SHARMA|ROHIT)\s+([A-Z][A-Za-z\s]+?)(?:\n|Age|\d)', 1),
            ],
            'age': [
                (r'Age\s*:?\s*(\d+)', 1),
                (r'Age\s+(\d+)\s*(?:Y|Yr)', 1),
            ],
            'date_collection': [
                (r'Collection\s+(?:on|date)\s*:?\s*(\d{1,2}-\d{1,2}-\d{4})', 1),
                (r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 1),
            ],
            'date_report': [
                (r'Report\s+(?:Date|Fecha)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})', 1),
            ],
            'test_type': [
                (r'(SEROLOGY|BIOCHEMISTRY|HEMATOLOGY|PATHOLOGY|IMMUNOLOGY)', 1),
            ],
            'hospital': [
                (r'(Manipal|SRV|RG\s+Stone|Oscar|OSCAR)', 1),
            ]
        }
        
        # Buscar cada patrón
        for key, pattern_list in patterns.items():
            for pattern, group_idx in pattern_list:
                try:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match and match.lastindex and match.lastindex >= group_idx:
                        data[key] = match.group(group_idx).strip()
                        break
                except (IndexError, AttributeError):
                    continue
        
        return data
    
    def extract_lab_values(self, text: str) -> List[Dict]:
        """
        Extraer valores de laboratorio del texto
        Busca patrón flexible: Nombre_Test | Valor | Unidad | [Rango]
        """
        values = []
        lines = text.split('\n')
        
        for line in lines:
            # Patrón 1: NOMBRE valor unidad [rango]
            match1 = re.search(
                r'([A-Z][A-Za-z\s\(\)]{3,}?)\s+(\d+\.?\d*)\s+([a-zA-Z/%]+)\s*\[?([\d\.\-\s]+?)?\]?$',
                line.strip()
            )
            
            # Patrón 2: NOMBRE | valor | unidad
            match2 = re.search(
                r'([A-Z][A-Za-z\s\(\)]{3,}?)\s*\|?\s+(\d+\.?\d*)\s*\|?\s+([a-zA-Z/%]+)',
                line
            )
            
            match = match1 or match2
            
            if match:
                try:
                    test_name = match.group(1).strip()
                    value_str = match.group(2)
                    unit = match.group(3).strip()
                    ref_range = match.group(4).strip() if match.lastindex >= 4 and match.group(4) else "N/A"
                    
                    # Validaciones
                    if len(test_name) > 3 and len(test_name) < 80:
                        value = float(value_str)
                        values.append({
                            'test': test_name,
                            'value': value,
                            'unit': unit,
                            'reference': ref_range,
                        })
                except (ValueError, AttributeError, IndexError):
                    continue
        
        return values
    
    def process_report(self, image_path: str) -> Dict:
        """
        Procesar informe completo
        Retorna diccionario con datos del paciente y laboratorio
        """
        try:
            # Extraer texto
            text, method = self.extract_text_smart(image_path)
            
            # Extraer datos estructurados
            patient_data = self.extract_patient_data(text)
            lab_values = self.extract_lab_values(text)
            
            result = {
                'file': Path(image_path).name,
                'status': 'success' if patient_data else 'partial',
                'method': method,
                'text_length': len(text),
                'patient': patient_data,
                'lab_values': lab_values,
                'raw_text': text[:500],  # Primeros 500 caracteres
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error procesando {image_path}: {e}")
            return {
                'file': Path(image_path).name,
                'status': 'error',
                'error': str(e)
            }
    
    def batch_process(self, image_dir: str) -> List[Dict]:
        """Procesar múltiples imágenes de un directorio"""
        image_dir = Path(image_dir)
        image_files = list(image_dir.glob('*.png')) + list(image_dir.glob('*.jpg'))
        
        results = []
        for i, img_path in enumerate(image_files, 1):
            logger.info(f"Procesando {i}/{len(image_files)}: {img_path.name}")
            result = self.process_report(str(img_path))
            results.append(result)
        
        return results


def print_diagnostics(results: List[Dict]):
    """Imprimir diagnóstico de resultados"""
    print("\n" + "="*80)
    print("📊 DIAGNÓSTICO DE ESCANEO OCR")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        print(f"\n📄 {i}. {result['file']}")
        print(f"   Estado: {result['status']}")
        
        if result['status'] != 'error':
            print(f"   Método: {result['method']}")
            print(f"   Caracteres extraídos: {result['text_length']}")
            
            if result['patient']:
                print(f"   Datos del paciente:")
                for key, val in result['patient'].items():
                    print(f"     • {key}: {val}")
            
            if result['lab_values']:
                print(f"   Valores de laboratorio encontrados: {len(result['lab_values'])}")
                for val in result['lab_values'][:3]:
                    print(f"     • {val['test']}: {val['value']} {val['unit']}")
                if len(result['lab_values']) > 3:
                    print(f"     ... y {len(result['lab_values']) - 3} más")
        else:
            print(f"   Error: {result.get('error', 'Desconocido')}")


if __name__ == "__main__":
    import sys
    
    # Si se pasa un directorio, procesar batch
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # Usar uploads como default
        target = '/mnt/user-data/uploads'
    
    scanner = EnhancedOCRScanner()
    
    if os.path.isdir(target):
        results = scanner.batch_process(target)
    else:
        results = [scanner.process_report(target)]
    
    # Mostrar diagnóstico
    print_diagnostics(results)
    
    # Guardar resultados en JSON
    output_file = '/home/claude/ocr_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        # Serializar para JSON (remover raw_text muy largo)
        json_results = []
        for r in results:
            r_copy = r.copy()
            if 'raw_text' in r_copy:
                r_copy['raw_text'] = r_copy['raw_text'][:100] + "..."
            json_results.append(r_copy)
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Resultados guardados en: {output_file}")
