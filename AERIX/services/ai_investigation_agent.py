"""
Phase 20 - AI Investigation Agent ⭐⭐⭐⭐⭐

This is your final layer - the complete AI investigation agent.

Workflow:
User Question → LLM Planner → Search Orchestrator → Investigation Service → 
Timeline Builder → Clip Retrieval → Final Answer

Supports compound investigation questions:
- "Show everyone who entered after 5:00 PM and stayed for more than 2 minutes"
- "Find the person with a backpack who appears near the checkout"
- "Give me all clips where the same person appears more than once"
- "Summarize the movement of the person in the blue shirt"

The LLM translates natural language into backend tool calls.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from sqlalchemy.orm import Session

from services.llm_intelligence import LLMIntelligence, SearchPlan
from services.search_orchestrator import SearchOrchestrator
from services.investigation_service_advanced import InvestigationService
from services.timeline_intelligence import TimelineIntelligence
from services.backend_hardening import robust_error_handler, hardening_service
from database.repository.conversation_memory_repository import (
    get_memory,
    save_memory,
    list_recent_memory,
)

logger = logging.getLogger(__name__)


@dataclass
class InvestigationResult:
    """Complete investigation result"""
    investigation_id: str
    query: str
    confidence: float
    summary: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    clips: List[Dict[str, Any]]
    insights: List[str]
    related_findings: List[Dict[str, Any]]
    execution_plan: Dict[str, Any]
    status: str
    timestamp: str


class AIInvestigationAgent:
    """
    Complete AI Investigation Agent
    
    This agent:
    1. Understands complex natural language queries
    2. Plans multi-step investigations
    3. Executes compound search operations
    4. Synthesizes results into coherent reports
    5. Provides explainable AI reasoning
    6. Handles edge cases gracefully
    """
    
    def __init__(self, use_mock_llm: bool = True):
        """Initialize AI Investigation Agent"""
        self.llm_intelligence = LLMIntelligence(use_mock_llm=use_mock_llm)
        self.search_orchestrator = SearchOrchestrator(use_mock_llm=use_mock_llm)
        self.investigation_service = InvestigationService()
        self.timeline_intelligence = TimelineIntelligence()
        
        # Compound query patterns
        self.compound_patterns = {
            'time_and_duration': ['after', 'before', 'stayed', 'more than', 'longer than'],
            'appearance_and_location': ['person', 'near', 'at', 'by'],
            'multiple_appearances': ['same person', 'appears', 'more than once', 'multiple'],
            'movement_summary': ['summarize', 'movement', 'path', 'journey', 'track'],
            'behavioral_analysis': ['behavior', 'pattern', 'activity', 'interaction'],
            'counting_queries': ['how many', 'count', 'total', 'number of']
        }
        
        logger.info("🤖 AI Investigation Agent initialized")
    
    @robust_error_handler("ai_investigation", log_errors=True)
    def investigate(
        self, 
        user_query: str, 
        db: Session,
        context: Optional[Dict] = None,
        max_results: int = 50,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> InvestigationResult:
        """
        Complete AI investigation based on natural language query.

        Phase 20: Accepts a conversation_id so that entity references
        ("he", "she", "they", "him", "her", "that person", "the same one")
        are resolved against prior results in the same conversation.

        Args:
            user_query: Natural language query from user
            db: Database session
            context: Optional context (video_id, time_range, etc.)
            max_results: Maximum results to return
            conversation_id: Conversation session ID for memory (Phase 20)
            user_id: Optional user UUID for memory scoping
            
        Returns:
            Complete investigation result
        """
        investigation_id = f"inv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"🕵️ Starting AI investigation: '{user_query}' (ID: {investigation_id})")
        
        with hardening_service.hardened_operation(f"ai_investigation_{investigation_id}", db) as tx:
            try:
                # ----------------------------------------------------------
                # Phase 20 — Resolve entity references from conversation memory
                # ----------------------------------------------------------
                resolved_query = user_query
                if conversation_id:
                    resolved_query = self._resolve_entities(user_query, conversation_id, db, context)
                    logger.info(f"🧠 Entity-resolved query: '{resolved_query}'")

                # Step 1: Analyze query complexity
                query_analysis = self._analyze_query_complexity(resolved_query)
                
                # Step 2: Generate investigation plan
                if query_analysis['is_compound']:
                    plan = self._plan_compound_investigation(resolved_query, context, query_analysis)
                else:
                    plan = self.llm_intelligence.parse_query(resolved_query, context)
                
                # Step 3: Execute investigation plan
                investigation_results = self._execute_investigation_plan(plan, db, context, max_results)
                
                # Step 4: Synthesize final answer
                final_result = self._synthesize_final_answer(
                    resolved_query, plan, investigation_results, investigation_id
                )

                # ----------------------------------------------------------
                # Phase 20 — Persist findings to conversation memory
                # ----------------------------------------------------------
                if conversation_id:
                    self._save_memory_from_result(
                        final_result, conversation_id, resolved_query, db, user_id
                    )
                
                logger.info(f"✅ AI investigation completed: {investigation_id}")
                return final_result
                
            except Exception as e:
                logger.error(f"❌ AI investigation failed: {investigation_id} - {e}")
                return self._create_error_result(investigation_id, user_query, str(e))
    
    # ------------------------------------------------------------------
    # Phase 20 — Conversation memory helpers
    # ------------------------------------------------------------------

    # Pronouns and anaphoric phrases that refer to a previously-identified track
    _ENTITY_PRONOUNS = {
        "he", "she", "they", "him", "her", "them",
        "that person", "the same person", "the same one",
        "this person", "the suspect", "the individual",
    }

    def _resolve_entities(
        self,
        query: str,
        conversation_id: str,
        db: Session,
        context: Optional[Dict],
    ) -> str:
        """
        Replace anaphoric references with concrete identifiers stored in memory.

        Example:
            Memory:  last_track_id = "Track 17"
            Input:   "Show where he stopped."
            Output:  "Show where Track 17 stopped."
        """
        query_lower = query.lower()

        # Check whether the query contains any pronoun / anaphoric phrase
        contains_pronoun = any(p in query_lower for p in self._ENTITY_PRONOUNS)
        if not contains_pronoun:
            return query  # nothing to resolve

        # Look up the most recently mentioned track
        memory = get_memory(db, conversation_id, "last_track_id")
        if not memory:
            # No prior context — return query unchanged
            logger.debug("No conversation memory found for id=%s", conversation_id)
            return query

        last_track = memory.memory_value  # e.g. "Track 17" or a UUID string

        # Replace the first pronoun found with the track reference
        resolved = query
        for pronoun in sorted(self._ENTITY_PRONOUNS, key=len, reverse=True):
            # Case-insensitive replacement of the first occurrence
            idx = resolved.lower().find(pronoun)
            if idx != -1:
                resolved = resolved[:idx] + last_track + resolved[idx + len(pronoun):]
                logger.info(
                    "Resolved pronoun '%s' → '%s' in query", pronoun, last_track
                )
                break

        return resolved

    def _save_memory_from_result(
        self,
        result: "InvestigationResult",
        conversation_id: str,
        resolved_query: str,
        db: Session,
        user_id: Optional[str],
    ) -> None:
        """
        Persist the most salient findings from this investigation so that
        subsequent turns can reference them by pronoun.

        Stores:
            last_query        — the (resolved) query text
            last_track_id     — the first matched track ID (if any)
            last_investigation_id — the investigation ID
        """
        try:
            # Always save last query
            save_memory(
                db,
                conversation_id=conversation_id,
                memory_key="last_query",
                memory_value=resolved_query,
                user_id=user_id,
            )

            # Save investigation ID
            save_memory(
                db,
                conversation_id=conversation_id,
                memory_key="last_investigation_id",
                memory_value=result.investigation_id,
                user_id=user_id,
            )

            # Save the first track ID found in evidence
            track_id = self._extract_primary_track(result)
            if track_id:
                save_memory(
                    db,
                    conversation_id=conversation_id,
                    memory_key="last_track_id",
                    memory_value=track_id,
                    user_id=user_id,
                )
                logger.info(
                    "💾 Saved conversation memory: last_track_id=%s (conv=%s)",
                    track_id,
                    conversation_id,
                )

            db.flush()
        except Exception as exc:
            # Memory persistence should never break the investigation
            logger.warning("Failed to save conversation memory: %s", exc)

    @staticmethod
    def _extract_primary_track(result: "InvestigationResult") -> Optional[str]:
        """Return the track_id of the highest-confidence evidence item, if any."""
        best_track: Optional[str] = None
        best_conf: float = -1.0
        for item in result.evidence or []:
            conf = float(item.get("confidence", 0.0))
            tid = item.get("track_id")
            if tid and conf > best_conf:
                best_conf = conf
                best_track = str(tid)
        # Also check timeline entries
        if not best_track:
            for entry in result.timeline or []:
                tid = entry.get("track_id")
                if tid:
                    best_track = str(tid)
                    break
        return best_track

    def _analyze_query_complexity(self, query: str) -> Dict[str, Any]:
        """
        Analyze if query is compound/complex
        
        Args:
            query: User query
            
        Returns:
            Query complexity analysis
        """
        query_lower = query.lower()
        
        analysis = {
            'is_compound': False,
            'complexity_score': 0,
            'detected_patterns': [],
            'estimated_steps': 1,
            'requires_multi_stage': False
        }
        
        # Check for compound patterns
        for pattern_type, keywords in self.compound_patterns.items():
            if any(keyword in query_lower for keyword in keywords):
                analysis['detected_patterns'].append(pattern_type)
                analysis['complexity_score'] += 1
        
        # Compound query indicators
        compound_indicators = [
            ' and ', ' who ', ' that ', ' where ', ' when ',
            'more than', 'less than', 'between', 'both', 'either'
        ]
        
        for indicator in compound_indicators:
            if indicator in query_lower:
                analysis['complexity_score'] += 1
        
        # Determine if compound
        if analysis['complexity_score'] >= 2:
            analysis['is_compound'] = True
            analysis['estimated_steps'] = min(analysis['complexity_score'], 5)
            analysis['requires_multi_stage'] = analysis['complexity_score'] >= 3
        
        logger.info(f"🧠 Query complexity analysis: {analysis}")
        return analysis
    
    def _plan_compound_investigation(
        self, 
        query: str, 
        context: Optional[Dict],
        query_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Plan complex compound investigation
        
        Args:
            query: User query
            context: Optional context
            query_analysis: Query complexity analysis
            
        Returns:
            Compound investigation plan
        """
        logger.info(f"📋 Planning compound investigation for: '{query}'")
        
        # Break down compound query into sub-queries
        sub_plans = []
        
        for pattern in query_analysis['detected_patterns']:
            if pattern == 'time_and_duration':
                sub_plans.append(self._create_temporal_sub_plan(query, context))
            elif pattern == 'appearance_and_location':
                sub_plans.append(self._create_visual_sub_plan(query, context))
            elif pattern == 'multiple_appearances':
                sub_plans.append(self._create_recurrence_sub_plan(query, context))
            elif pattern == 'movement_summary':
                sub_plans.append(self._create_movement_sub_plan(query, context))
            elif pattern == 'behavioral_analysis':
                sub_plans.append(self._create_behavior_sub_plan(query, context))
            elif pattern == 'counting_queries':
                sub_plans.append(self._create_counting_sub_plan(query, context))
        
        return {
            'query_type': 'compound_investigation',
            'original_query': query,
            'complexity_score': query_analysis['complexity_score'],
            'sub_plans': sub_plans,
            'execution_strategy': 'sequential' if query_analysis['requires_multi_stage'] else 'parallel',
            'estimated_duration': query_analysis['estimated_steps'] * 5  # seconds
        }
    
    def _create_temporal_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create temporal filtering sub-plan"""
        return {
            'plan_type': 'temporal_filter',
            'description': 'Filter events by time and duration criteria',
            'actions': ['search_time_range', 'filter_by_duration'],
            'priority': 1  # Execute first
        }
    
    def _create_visual_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create visual appearance sub-plan"""
        return {
            'plan_type': 'visual_search',
            'description': 'Search by visual appearance and location',
            'actions': ['search_embeddings', 'search_text', 'filter_by_location'],
            'priority': 2
        }
    
    def _create_recurrence_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create recurrence analysis sub-plan"""
        return {
            'plan_type': 'recurrence_analysis',
            'description': 'Find people who appear multiple times',
            'actions': ['find_similar', 'analyze_recurrence', 'build_timeline'],
            'priority': 3
        }
    
    def _create_movement_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create movement analysis sub-plan"""
        return {
            'plan_type': 'movement_analysis',
            'description': 'Analyze movement patterns and paths',
            'actions': ['analyze_movement', 'build_timeline', 'summarize_journey'],
            'priority': 2
        }
    
    def _create_behavior_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create behavior analysis sub-plan"""
        return {
            'plan_type': 'behavior_analysis',
            'description': 'Analyze behavioral patterns',
            'actions': ['analyze_behavior', 'detect_patterns', 'generate_insights'],
            'priority': 3
        }
    
    def _create_counting_sub_plan(self, query: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Create counting/statistics sub-plan"""
        return {
            'plan_type': 'statistical_analysis',
            'description': 'Generate counts and statistics',
            'actions': ['count_objects', 'generate_statistics'],
            'priority': 1
        }
    
    def _execute_investigation_plan(
        self,
        plan: Dict[str, Any],
        db: Session,
        context: Optional[Dict],
        max_results: int
    ) -> Dict[str, Any]:
        """Execute investigation plan (simple or compound)"""
        
        if plan.get('query_type') == 'compound_investigation':
            return self._execute_compound_plan(plan, db, context, max_results)
        else:
            # Simple plan execution
            return self.search_orchestrator.execute_search_plan(plan, db, context, max_results)
    
    def _execute_compound_plan(
        self,
        compound_plan: Dict[str, Any],
        db: Session,
        context: Optional[Dict],
        max_results: int
    ) -> Dict[str, Any]:
        """Execute compound investigation plan"""
        
        logger.info(f"🔄 Executing compound plan with {len(compound_plan['sub_plans'])} sub-plans")
        
        execution_results = {
            'compound_execution': True,
            'sub_results': {},
            'merged_results': [],
            'execution_order': [],
            'total_results': 0
        }
        
        # Sort sub-plans by priority
        sub_plans = sorted(compound_plan['sub_plans'], key=lambda x: x.get('priority', 999))
        
        # Execute sub-plans
        intermediate_results = {}
        
        for i, sub_plan in enumerate(sub_plans):
            plan_type = sub_plan['plan_type']
            logger.info(f"📋 Executing sub-plan {i+1}/{len(sub_plans)}: {plan_type}")
            
            try:
                # Convert sub-plan to SearchPlan format
                search_plan = self._convert_sub_plan_to_search_plan(sub_plan, compound_plan['original_query'])
                
                # Execute sub-plan
                sub_result = self.search_orchestrator.execute_search_plan(search_plan, db, context, max_results)
                
                execution_results['sub_results'][plan_type] = sub_result
                execution_results['execution_order'].append(plan_type)
                
                # Store for next sub-plan if needed
                intermediate_results[plan_type] = sub_result
                
                logger.info(f"✅ Sub-plan completed: {plan_type} - {len(sub_result.get('results', []))} results")
                
            except Exception as e:
                logger.error(f"❌ Sub-plan failed: {plan_type} - {e}")
                execution_results['sub_results'][plan_type] = {'error': str(e), 'status': 'failed'}
        
        # Merge and filter results based on compound criteria
        execution_results['merged_results'] = self._merge_compound_results(
            execution_results['sub_results'], compound_plan
        )
        
        execution_results['total_results'] = len(execution_results['merged_results'])
        
        logger.info(f"✅ Compound plan executed: {execution_results['total_results']} final results")
        
        return execution_results
    
    def _convert_sub_plan_to_search_plan(self, sub_plan: Dict, original_query: str) -> SearchPlan:
        """Convert sub-plan to SearchPlan format"""
        from services.llm_intelligence import SearchPlan, ActionType
        
        # Map action names to ActionType enums
        action_mapping = {
            'search_time_range': ActionType.SEARCH_TIME_RANGE,
            'filter_by_duration': ActionType.TRACK_DURATION,
            'search_embeddings': ActionType.SEARCH_EMBEDDINGS,
            'search_text': ActionType.SEARCH_TEXT,
            'find_similar': ActionType.FIND_SIMILAR,
            'analyze_movement': ActionType.ANALYZE_MOVEMENT,
            'count_objects': ActionType.COUNT_OBJECTS,
            'build_timeline': ActionType.BUILD_TIMELINE,
            'retrieve_clips': ActionType.RETRIEVE_CLIPS
        }
        
        actions = [action_mapping.get(action, ActionType.SEARCH_TEXT) for action in sub_plan.get('actions', [])]
        
        return SearchPlan(
            query_type=sub_plan['plan_type'],
            primary_object='person',
            attributes={},
            temporal_constraints={},
            spatial_constraints={},
            actions=actions,
            confidence=0.8,
            reasoning=sub_plan['description']
        )
    
    def _merge_compound_results(
        self,
        sub_results: Dict[str, Any],
        compound_plan: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Merge results from multiple sub-plans based on compound logic"""
        
        logger.info("🔗 Merging compound investigation results")
        
        # Start with all results
        all_results = []
        for plan_type, result in sub_results.items():
            if result.get('status') == 'success' and 'results' in result:
                for item in result['results']:
                    item['source_plan'] = plan_type
                    all_results.append(item)
        
        # Apply compound filtering logic
        # For demonstration, we'll implement basic AND logic
        # In production, this would be more sophisticated
        
        if len(sub_results) > 1:
            # Find results that satisfy multiple criteria
            result_groups = {}
            
            # Group by track_id if available
            for result in all_results:
                track_id = result.get('track_id')
                if track_id:
                    if track_id not in result_groups:
                        result_groups[track_id] = []
                    result_groups[track_id].append(result)
            
            # Keep tracks that appear in multiple sub-results (AND logic)
            merged_results = []
            for track_id, track_results in result_groups.items():
                source_plans = set(r['source_plan'] for r in track_results)
                if len(source_plans) > 1:  # Appears in multiple sub-plans
                    # Merge information from all sub-plans
                    merged_result = self._merge_track_results(track_results)
                    merged_results.append(merged_result)
            
            return merged_results[:50]  # Limit results
        
        return all_results[:50]
    
    def _merge_track_results(self, track_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple results for the same track"""
        
        base_result = track_results[0].copy()
        base_result['compound_match'] = True
        base_result['matching_criteria'] = list(set(r['source_plan'] for r in track_results))
        base_result['confidence'] = sum(r.get('confidence', r.get('similarity', 0.5)) for r in track_results) / len(track_results)
        
        return base_result
    
    def _synthesize_final_answer(
        self,
        original_query: str,
        plan: Dict[str, Any],
        investigation_results: Dict[str, Any],
        investigation_id: str
    ) -> InvestigationResult:
        """Synthesize final investigation answer"""
        
        logger.info(f"🎯 Synthesizing final answer for: {investigation_id}")
        
        # Extract key information
        results = investigation_results.get('merged_results', investigation_results.get('results', []))
        timeline = investigation_results.get('timeline', [])
        clips = investigation_results.get('clips', [])
        
        # Generate insights
        insights = self._generate_investigation_insights(original_query, results, timeline)
        
        # Create summary
        summary = {
            'total_matches': len(results),
            'confidence': plan.get('confidence', 0.8),
            'query_complexity': plan.get('complexity_score', 1),
            'evidence_clips': len(clips),
            'timeline_events': len(timeline),
            'execution_time': datetime.now().isoformat()
        }
        
        # Format evidence
        evidence = [self._format_evidence_item(result) for result in results[:20]]
        
        # Related findings
        related_findings = self._find_related_evidence(results, original_query)
        
        return InvestigationResult(
            investigation_id=investigation_id,
            query=original_query,
            confidence=summary['confidence'],
            summary=summary,
            evidence=evidence,
            timeline=timeline,
            clips=clips,
            insights=insights,
            related_findings=related_findings,
            execution_plan=plan,
            status='success',
            timestamp=datetime.now().isoformat()
        )
    
    def _generate_investigation_insights(
        self,
        query: str,
        results: List[Dict],
        timeline: List[Dict]
    ) -> List[str]:
        """Generate insights from investigation results"""
        
        insights = []
        
        if not results:
            insights.append("No matches found for the specified criteria")
            return insights
        
        # Quantity insights
        if len(results) == 1:
            insights.append("Found exactly one matching person")
        elif len(results) > 10:
            insights.append(f"High number of matches ({len(results)}) - consider refining criteria")
        else:
            insights.append(f"Found {len(results)} people matching the criteria")
        
        # Time-based insights
        if timeline:
            time_span = self._calculate_time_span(timeline)
            if time_span:
                insights.append(f"Activity occurred over {time_span}")
        
        # Pattern insights
        compound_matches = [r for r in results if r.get('compound_match')]
        if compound_matches:
            insights.append(f"{len(compound_matches)} people met all specified criteria")
        
        return insights
    
    def _calculate_time_span(self, timeline: List[Dict]) -> str:
        """Calculate time span from timeline"""
        if len(timeline) < 2:
            return None
        
        timestamps = [t.get('timestamp') for t in timeline if t.get('timestamp')]
        if not timestamps:
            return None
        
        try:
            start_time = min(timestamps)
            end_time = max(timestamps)
            # Simple time span calculation
            return f"{start_time} to {end_time}"
        except:
            return None
    
    def _format_evidence_item(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format evidence item for response"""
        return {
            'type': result.get('result_type', 'match'),
            'confidence': result.get('confidence', result.get('similarity', 0.8)),
            'timestamp': result.get('timestamp'),
            'track_id': result.get('track_id'),
            'description': self._generate_evidence_description(result),
            'metadata': result.get('metadata', {})
        }
    
    def _generate_evidence_description(self, result: Dict[str, Any]) -> str:
        """Generate human-readable evidence description"""
        
        if result.get('compound_match'):
            criteria = ', '.join(result.get('matching_criteria', []))
            return f"Person matching multiple criteria: {criteria}"
        
        result_type = result.get('result_type', 'match')
        
        if result_type == 'duration_match':
            duration = result.get('duration_seconds', 0)
            return f"Person visible for {duration} seconds"
        elif result_type == 'time_match':
            return "Person appeared during specified time period"
        elif result_type == 'embedding_match':
            similarity = result.get('similarity', 0)
            return f"Visual similarity match (confidence: {similarity:.2f})"
        else:
            return "Person matching search criteria"
    
    def _find_related_evidence(self, results: List[Dict], query: str) -> List[Dict[str, Any]]:
        """Find related evidence that might be relevant"""
        
        # For now, return empty list
        # In production, this would find related tracks, similar appearances, etc.
        return []
    
    def _create_error_result(
        self, 
        investigation_id: str, 
        query: str, 
        error_message: str
    ) -> InvestigationResult:
        """Create error result for failed investigation"""
        
        return InvestigationResult(
            investigation_id=investigation_id,
            query=query,
            confidence=0.0,
            summary={'error': error_message, 'status': 'failed'},
            evidence=[],
            timeline=[],
            clips=[],
            insights=[f"Investigation failed: {error_message}"],
            related_findings=[],
            execution_plan={},
            status='error',
            timestamp=datetime.now().isoformat()
        )


# Global AI Investigation Agent instance
from backend.core.config import settings
ai_investigation_agent = AIInvestigationAgent(use_mock_llm=settings.USE_MOCK_LLM)