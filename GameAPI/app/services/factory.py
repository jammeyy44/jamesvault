"""
Factory for creating game service instances based on provider name.
"""

from .category1_service import Category1Service
from .category2_service import Category2Service
from .category3_service import Category3Service
from .category4_service import Category4Service

class GameServiceFactory:
    @staticmethod
    def create_service(provider_name):
        providers = {
            "Gameroom": Category1Service,
            "CashMachine": Category1Service,
            "MrAllInOne": Category1Service,
            "Mafia": Category1Service,
            "CashFrenzy": Category1Service,
            "GameVault": Category2Service,
            "VegasSweeps": Category2Service,
            "Juwa": Category2Service,
            "FireKirin": Category3Service,
            "PandaMaster": Category3Service,
            "Milkyway": Category3Service,
            "OrionStars": Category3Service,
            "Vblink": Category4Service,
            "UltraPanda": Category4Service,
            "Egame": Category4Service,
            "RiverSweeps": Category4Service
        }
        service_class = providers.get(provider_name)
        if not service_class:
            raise ValueError(f"Unsupported provider: {provider_name}")
        return service_class(provider_name)