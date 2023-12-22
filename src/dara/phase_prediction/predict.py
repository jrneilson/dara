"""Code for predicting products in a chemical reaction."""
from dara.icsd import ICSDDatabase
from monty.json import MSONable


class PhasePredictor(MSONable):
    """Predict phases during solid-state synthesis."""

    def __init__(self, engine="reaction_network"):
        """Initialize the engine."""
        if engine == "reaction_network":
            from dara.phase_prediction.rn import ReactionNetworkEngine

            self.engine = ReactionNetworkEngine()

    def predict(
        self,
        reactants,
        temperature=1000,
        open_elem=None,
        chempot=0.0,
    ) -> dict[str, float]:
        """Predict and rank the probability of appearance of products of a chemical reaction."""
        return self.engine.predict(reactants=reactants, temperature=temperature, open_elem=open_elem, chempot=chempot)

    def write_cifs(self, use_icsd=True):
        """Write CIFs of the predicted products."""
        db = ICSDDatabase()
