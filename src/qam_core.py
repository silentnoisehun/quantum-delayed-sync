# -*- coding: utf-8 -*-
"""
QAM Core — IBM Quantum integrátor
=================================
A QAM architektura szinkronizalasi retegenek integratora.

Hasznalat:
  from qam_core import QAM
  qam = QAM(token="...", backend="ibm_kingston")
  backend = qam.backend
"""
import json, os, sys
from typing import Optional, Dict, Any

class QAM:
    """
    QAM integrator a quantum-sync es egyeb QAM projektek szamara.

    A token ket forrasbol toltoztatik be:
    1. Explicit konstruktor parameter (elnyomja minden mas forrast)
    2. IBM_TOKEN_PATH kornyezeti valtozo (apikey.json formatum)
    3. Alapertelmezett eleresi ut (QAM konvencio)

    Attributes:
        backend: Aktiv IBM backend objektum
        backend_name: Backend neve (pl. ibm_kingston)
        qubit: Kalibralt jol qubit sorszam
    """

    DEFAULT_TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ibm_token.json")

    def __init__(self, token: Optional[str] = None, backend: str = "ibm_kingston", qubit: int = 91):
        self.backend_name = backend
        self.qubit = qubit

        # Token betoltese
        if token:
            self.token = token
        else:
            path = os.environ.get("IBM_TOKEN_PATH", self.DEFAULT_TOKEN_PATH)
            if os.path.exists(path):
                with open(path, "r") as f:
                    creds = json.load(f)
                self.token = creds.get("apikey")
                if not self.token:
                    raise ValueError(f"Nincs apikey a {path}-bol")
                print(f"Token betoltve: {path} -> apikey.json (len={len(self.token)})")
            else:
                raise FileNotFoundError(f"Nincs token: {path} vagy IBM_TOKEN_PATH nem beallitva")

        # Backend inicializalasa
        self._init_backend()

    def _init_backend(self):
        """IBM backend inicializalasa (qiskit-ibm-runtime, modern API)."""
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService
        except ImportError as e:
            raise ImportError(
                "qiskit-ibm-runtime szukseges a hardver modhoz "
                "(a qiskit_ibm_provider legacy csomag már nem elérhető)") from e
        try:
            self.service = QiskitRuntimeService(
                channel="ibm_quantum_platform", token=self.token, instance="auto")
            self.backend = self.service.backend(name=self.backend_name)
            print(f"Backend inicializalva: {self.backend_name}")

            # Qubit adatok kiirasa
            try:
                props = self.backend.qubit_properties(self.qubit)
                if props.t1 and props.t2:
                    print(f"  Qubit {self.qubit}: T1={props.t1*1e6:.1f}us "
                          f"T2={props.t2*1e6:.1f}us")
            except Exception as e:
                print(f"  qubit_properties nem elerheto: {e}")
        except Exception as e:
            raise ConnectionError(f"Nem sikerult csatlakozni az IBM-hez: {e}") from e


if __name__ == "__main__":
    qam = QAM(backend="ibm_kingston", qubit=91)
    print(f"Backend: {qam.backend_name}")
