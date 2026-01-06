"""
Core Policy Engine
"""
import json
import yaml
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum
import logging

from ..models.rule import Rule, RuleSet, Condition, Action
from ..models.fact import Fact, FactBase
from ..models.decision import Decision, DecisionResult
from ..models.policy import Policy, PolicyVersion
from .evaluator import RuleEvaluator
from .validator import RuleValidator
from .compiler import RuleCompiler
from ..utils.logger import get_logger
from ..utils.cache import CacheManager

logger = get_logger(__name__)

class EngineMode(Enum):
    """Engine operating modes"""
    STRICT = "strict"      # Stop on first failure
    LENIENT = "lenient"    # Continue on failure
    DEBUG = "debug"        # Debug mode with detailed output

class PolicyEngine:
    """Main policy engine class"""
    
    def __init__(
        self,
        mode: EngineMode = EngineMode.STRICT,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        self.mode = mode
        self.evaluator = RuleEvaluator(mode=mode)
        self.validator = RuleValidator()
        self.compiler = RuleCompiler()
        self.cache = CacheManager(enabled=cache_enabled, ttl=cache_ttl)
        
        # Registry for loaded policies
        self._policies: Dict[str, Policy] = {}
        self._rule_sets: Dict[str, RuleSet] = {}
        
    def load_policy(
        self,
        policy_data: Union[Dict, str],
        policy_id: Optional[str] = None,
        format: str = "json"
    ) -> Policy:
        """Load a policy from data"""
        
        # Parse input data
        if isinstance(policy_data, str):
            if format == "json":
                data = json.loads(policy_data)
            elif format == "yaml":
                data = yaml.safe_load(policy_data)
            else:
                raise ValueError(f"Unsupported format: {format}")
        else:
            data = policy_data
            
        # Validate policy structure
        self.validator.validate_policy_structure(data)
        
        # Create policy object
        policy = Policy.model_validate(data)
        
        # Set ID if provided
        if policy_id:
            policy.id = policy_id
            
        # Store in registry
        self._policies[policy.id] = policy
        
        # Compile rules
        self._compile_policy_rules(policy)
        
        logger.info(f"Loaded policy: {policy.id} v{policy.version}")
        return policy
        
    def _compile_policy_rules(self, policy: Policy):
        """Compile all rules in a policy"""
        for rule_set in policy.rule_sets.values():
            compiled = self.compiler.compile_rule_set(rule_set)
            self._rule_sets[rule_set.id] = compiled
            
    def evaluate_eligibility(
        self,
        policy_id: str,
        applicant_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Decision:
        """Evaluate eligibility for a policy"""
        
        # Check cache
        cache_key = f"eligibility:{policy_id}:{hash(str(applicant_data))}"
        cached = self.cache.get(cache_key)
        if cached:
            return Decision.model_validate(cached)
            
        # Get policy
        if policy_id not in self._policies:
            raise ValueError(f"Policy not found: {policy_id}")
            
        policy = self._policies[policy_id]
        
        # Create facts
        facts = self._create_facts(applicant_data, context)
        
        # Evaluate each rule set
        results = []
        for rule_set_id, rule_set in policy.rule_sets.items():
            if rule_set.enabled:
                result = self.evaluator.evaluate_rule_set(
                    rule_set, 
                    facts, 
                    context or {}
                )
                results.append(result)
                
        # Create final decision
        decision = Decision(
            policy_id=policy_id,
            policy_version=policy.version,
            timestamp=datetime.utcnow(),
            applicant_id=applicant_data.get("id"),
            results=results,
            overall_eligible=self._determine_overall_eligibility(results),
            metadata={
                "engine_mode": self.mode.value,
                "facts_processed": len(facts),
                "rules_evaluated": sum(len(r.rule_set.rules) for r in results)
            }
        )
        
        # Cache result
        self.cache.set(cache_key, decision.model_dump())
        
        return decision
        
    def evaluate_compliance(
        self,
        rule_set_id: str,
        entity_data: Dict[str, Any],
        thresholds: Optional[Dict[str, Any]] = None
    ) -> List[DecisionResult]:
        """Evaluate compliance against a rule set"""
        
        if rule_set_id not in self._rule_sets:
            raise ValueError(f"Rule set not found: {rule_set_id}")
            
        rule_set = self._rule_sets[rule_set_id]
        facts = self._create_facts(entity_data)
        
        if thresholds:
            facts.update(self._create_facts(thresholds, prefix="threshold_"))
            
        return self.evaluator.evaluate_rule_set(rule_set, facts).results
        
    def check_thresholds(
        self,
        rule_set_id: str,
        values: Dict[str, float],
        thresholds: Dict[str, Dict[str, float]]
    ) -> Dict[str, Dict[str, bool]]:
        """Check values against thresholds"""
        
        results = {}
        for key, value in values.items():
            if key in thresholds:
                threshold_rules = thresholds[key]
                key_results = {}
                
                for op, threshold in threshold_rules.items():
                    if op == "min":
                        key_results["meets_minimum"] = value >= threshold
                    elif op == "max":
                        key_results["exceeds_maximum"] = value > threshold
                    elif op == "target":
                        key_results["at_target"] = value == threshold
                    elif op == "range_min":
                        key_results["in_range_min"] = value >= threshold
                    elif op == "range_max":
                        key_results["in_range_max"] = value <= threshold
                        
                results[key] = key_results
                
        return results
        
    def _create_facts(
        self, 
        data: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None,
        prefix: str = ""
    ) -> Dict[str, Fact]:
        """Create facts from data dictionary"""
        
        facts = {}
        
        # Add data facts
        for key, value in data.items():
            fact_key = f"{prefix}{key}" if prefix else key
            facts[fact_key] = Fact(
                name=fact_key,
                value=value,
                source="input",
                timestamp=datetime.utcnow()
            )
            
        # Add context facts
        if context:
            for key, value in context.items():
                fact_key = f"context_{key}"
                facts[fact_key] = Fact(
                    name=fact_key,
                    value=value,
                    source="context",
                    timestamp=datetime.utcnow()
                )
                
        # Add engine facts
        facts["engine_timestamp"] = Fact(
            name="engine_timestamp",
            value=datetime.utcnow().isoformat(),
            source="engine",
            timestamp=datetime.utcnow()
        )
        
        return facts
        
    def _determine_overall_eligibility(
        self, 
        results: List[DecisionResult]
    ) -> bool:
        """Determine overall eligibility from results"""
        
        if not results:
            return False
            
        # Check if all required rules passed
        for result in results:
            if result.rule.required and not result.passed:
                return False
                
        # Check if minimum passing percentage met
        total_rules = sum(len(r.rule_set.rules) for r in results)
        passed_rules = sum(r.passed_rules_count for r in results)
        
        if total_rules > 0:
            pass_rate = passed_rules / total_rules
            return pass_rate >= 0.8  # 80% threshold
            
        return False
        
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID"""
        return self._policies.get(policy_id)
        
    def list_policies(self) -> List[str]:
        """List all loaded policy IDs"""
        return list(self._policies.keys())
        
    def clear_cache(self):
        """Clear engine cache"""
        self.cache.clear()
        logger.info("Engine cache cleared")
        
    def export_policy(self, policy_id: str, format: str = "json") -> str:
        """Export policy to specified format"""
        
        if policy_id not in self._policies:
            raise ValueError(f"Policy not found: {policy_id}")
            
        policy = self._policies[policy_id]
        
        if format == "json":
            return policy.model_dump_json(indent=2)
        elif format == "yaml":
            return yaml.dump(policy.model_dump(), default_flow_style=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")
