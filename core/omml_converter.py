import os
import re
from typing import Optional
from lxml import etree
import latex2mathml.converter

class OMMLConverter:
    _transform = None
    _xslt_found = False
    UNIT_NAMES = r'm|cm|dm|mm|km|km/h|km/giờ|km/phút|m/giây|m/phút|g|kg|g/cm|inch|giây|giờ|phút|lần|đồng|đồng/kg|mét|ha|s|h'
    UNIT_PATTERN = rf'(?:{UNIT_NAMES}|\(\s*(?:{UNIT_NAMES})\s*\))'

    @classmethod
    def _init_xslt(cls):
        if cls._transform is not None:
            return
        
        possible_paths = [
            r"C:\Program Files\Microsoft Office\Root\Office16\MML2OMML.XSL",
            r"C:\Program Files (x86)\Microsoft Office\Root\Office16\MML2OMML.XSL",
            r"C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL",
            r"C:\Program Files (x86)\Microsoft Office\Office16\MML2OMML.XSL",
            r"C:\Program Files\Microsoft Office\Office15\MML2OMML.XSL",
            r"C:\Program Files (x86)\Microsoft Office\Office15\MML2OMML.XSL"
        ]
        
        xslt_path = None
        for p in possible_paths:
            if os.path.exists(p):
                xslt_path = p
                break
                
        if xslt_path:
            try:
                xslt_doc = etree.parse(xslt_path)
                cls._transform = etree.XSLT(xslt_doc)
                cls._xslt_found = True
            except Exception:
                cls._xslt_found = False
        else:
            cls._xslt_found = False

    @classmethod
    def latex_to_omml(cls, latex_str: str) -> Optional[etree._Element]:
        """
        Converts a LaTeX formula string into an OMML XML Element (<m:oMath>).
        Returns None if conversion fails.
        """
        cls._init_xslt()
        if not cls._xslt_found or cls._transform is None:
            return None

        latex_clean = latex_str.strip()
        if not latex_clean:
            return None

        # Pre-clean LaTeX syntax for latex2mathml
        # 0. Heal broken LaTeX commands / escape artifacts and ext on units
        latex_clean = re.sub(r'\x09ext\b', r'\\text', latex_clean)
        latex_clean = re.sub(r'\\ext\{([^}]+)\}', r'\\text{\1}', latex_clean)
        latex_clean = re.sub(rf'\\ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', latex_clean)
        latex_clean = re.sub(r'\\ext\b', r'\\text', latex_clean)
        latex_clean = re.sub(r'(?<![a-zA-Z\\])ext\{([^}]+)\}', r'\\text{\1}', latex_clean)
        latex_clean = re.sub(rf'(?<![a-zA-Z\\])ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', latex_clean)
        latex_clean = re.sub(rf'(\d+(?:\{{,}}\d+)?)\s*\\text\{{\s*({cls.UNIT_PATTERN})\s*\}}', r'\1\\text{ \2}', latex_clean)

        # 0a. Normalize double backslashes before LaTeX commands: \\dfrac -> \dfrac, \\in -> \in
        latex_clean = re.sub(r'\\{2,}([a-zA-Z]+)', r'\\\1', latex_clean)
        # 0b. Expand shorthand fractions: \frac12 -> \frac{1}{2}
        latex_clean = re.sub(r'\\d?frac([0-9a-zA-Z])([0-9a-zA-Z])(?![a-zA-Z])', r'\\frac{\1}{\2}', latex_clean)
        # 1. replace \dfrac with \frac
        latex_clean = re.sub(r'\\dfrac(?=\{)', r'\\frac', latex_clean)
        # 2. replace {,} with ,
        latex_clean = latex_clean.replace(r'{,}', ',')
        # 3. replace \parallel with \Vert or \parallel
        latex_clean = latex_clean.replace(r'\parallel', r'\Vert')
        # 4. replace common spaces
        latex_clean = latex_clean.replace(r'\;', ' ').replace(r'\,', ' ').replace(r'\ ', ' ')
        # 5. replace \cdot
        latex_clean = latex_clean.replace(r'\cdot', r'*')

        try:
            mathml = latex2mathml.converter.convert(latex_clean)
            mml_doc = etree.fromstring(mathml.encode('utf-8'))
            omml_tree = cls._transform(mml_doc)
            return omml_tree.getroot()
        except Exception:
            return None
