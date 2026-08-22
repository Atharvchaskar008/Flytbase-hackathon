"""
AI Investigation API - The Final Phase 20 Implementation

This API endpoint demonstrates the complete AI investigation system with:
- Natural language query understanding
- Compound query support  
- LLM-guided intelligence
- Robust error handling
- Complete pipeline orchestration

Example queries:
- "Find the man wearing the red cap near the entrance"
- "Show everyone who entered after 5:00 PM and stayed for more than 2 minutes"
- "Give me all clips where the same person appears more than once"
- "Summarize the movement of the person in the blue shirt"
"""

from fastapi import APIRouter, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import uuid

from database.session import get_db
from services.ai_investigation_agent import ai_investigation_agent, AIInvestigationAgent
from services.backend_hardening import harden_api_endpoint

router = APIRouter(prefix="/ai", tags=["ai_investigation"])


@router.post("/investigate")
@harden_api_endpoint("ai_investigate")
async def investigate_with_ai(
    query: str = Form(..., description="Natural language investigation query"),
    video_id: Optional[str] = Form(None, description="Optional video ID to limit search scope"),
    max_results: int = Form(50, description="Maximum number of results to return"),
    include_clips: bool = Form(True, description="Whether to include video clips"),
    conversation_id: Optional[str] = Form(None, description="Conversation ID for memory (Phase 20)"),
    user_id: Optional[str] = Form(None, description="Optional user ID for memory scoping"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Complete AI-powered investigation
    
    This endpoint supports complex queries like:
    - "Find the person in the red shirt who stayed more than 5 minutes"
    - "Show me everyone who entered after 3 PM and went to the checkout area"
    - "Find people who appear multiple times in different videos"
    - "Summarize the behavior of the person with the backpack"
    
    Args:
        query: Natural language investigation query
        video_id: Optional video ID to limit search scope
        max_results: Maximum number of results (default: 50)
        include_clips: Whether to include video clips in response
        db: Database session
        
    Returns:
        Complete investigation results with evidence, timeline, and insights
    """
    
    # Validate query
    if not query or len(query.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Query must be at least 3 characters long"
        )
    
    # Prepare context
    context = {}
    if video_id:
        try:
            context['video_id'] = str(uuid.UUID(video_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid video ID format")
    
    # Execute AI investigation
    result = ai_investigation_agent.investigate(
        user_query=query.strip(),
        db=db,
        context=context,
        max_results=max_results,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    
    # Format response
    response = {
        'investigation_id': result.investigation_id,
        'query': result.query,
        'status': result.status,
        'timestamp': result.timestamp,
        'conversation_id': conversation_id,  # echo back for client to reuse
        
        'summary': {
            'confidence': result.confidence,
            'total_matches': result.summary.get('total_matches', 0),
            'evidence_clips': result.summary.get('evidence_clips', 0),
            'timeline_events': result.summary.get('timeline_events', 0),
            'query_complexity': result.summary.get('query_complexity', 1)
        },
        
        'evidence': result.evidence,
        'timeline': result.timeline if result.timeline else [],
        'clips': result.clips if include_clips else [],
        'insights': result.insights,
        'related_findings': result.related_findings,
        
        'ai_analysis': {
            'execution_plan': result.execution_plan,
            'reasoning': 'AI-powered investigation with multi-step analysis',
            'capabilities_used': [
                'natural_language_processing',
                'computer_vision_search', 
                'temporal_analysis',
                'behavioral_pattern_recognition'
            ]
        }
    }
    
    return response


@router.post("/investigate/compound")
@harden_api_endpoint("ai_compound_investigate")
async def compound_investigation(
    query: str = Form(..., description="Complex compound query"),
    filters: Optional[str] = Form(None, description="Additional JSON filters"),
    max_results: int = Form(30, description="Maximum results per sub-query"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle complex compound investigations
    
    Examples:
    - "Find people who entered after 5 PM AND stayed more than 2 minutes"
    - "Show me the person with red cap OR blue shirt near entrance"
    - "Everyone who appears in multiple cameras AND carries a bag"
    
    Args:
        query: Complex compound query
        filters: Optional additional JSON filters
        max_results: Maximum results per sub-query
        db: Database session
        
    Returns:
        Compound investigation results
    """
    
    # Parse additional filters if provided
    additional_context = {}
    if filters:
        try:
            import json
            additional_context = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in filters")
    
    # Execute compound investigation
    result = ai_investigation_agent.investigate(
        user_query=query,
        db=db,
        context=additional_context,
        max_results=max_results
    )
    
    # Enhanced response for compound queries
    response = {
        'investigation_id': result.investigation_id,
        'compound_query': True,
        'query': result.query,
        'status': result.status,
        
        'compound_analysis': {
            'complexity_score': result.summary.get('query_complexity', 1),
            'sub_queries_executed': len(result.execution_plan.get('sub_plans', [])),
            'merge_strategy': result.execution_plan.get('execution_strategy', 'sequential'),
            'total_processing_time': result.summary.get('execution_time', 'unknown')
        },
        
        'results': {
            'total_matches': len(result.evidence),
            'evidence': result.evidence,
            'timeline': result.timeline,
            'clips': result.clips,
            'confidence': result.confidence
        },
        
        'insights': result.insights,
        'explanation': 'Compound query processed using multi-stage AI analysis'
    }
    
    return response


@router.get("/capabilities")
async def get_ai_capabilities() -> Dict[str, Any]:
    """
    Get AI investigation capabilities
    
    Returns:
        Available AI investigation capabilities and example queries
    """
    
    return {
        'ai_investigation_capabilities': {
            'natural_language_processing': True,
            'compound_query_support': True,
            'visual_similarity_search': True,
            'temporal_analysis': True,
            'behavioral_pattern_recognition': True,
            'multi_camera_tracking': True,
            'evidence_clip_generation': True
        },
        
        'supported_query_types': [
            {
                'type': 'person_appearance',
                'description': 'Search by visual appearance',
                'examples': [
                    'Find the person wearing a red cap',
                    'Show me the man in blue shirt',
                    'Locate person with backpack'
                ]
            },
            {
                'type': 'temporal_queries', 
                'description': 'Time-based searches',
                'examples': [
                    'Show everyone who entered after 5 PM',
                    'Find people present between 2 PM and 4 PM',
                    'Who was here before 9 AM?'
                ]
            },
            {
                'type': 'duration_queries',
                'description': 'Duration and stay time analysis',
                'examples': [
                    'People who stayed more than 10 minutes',
                    'Show brief appearances under 30 seconds',
                    'Find long-term visitors'
                ]
            },
            {
                'type': 'behavioral_queries',
                'description': 'Movement and behavior patterns',
                'examples': [
                    'Summarize the movement of person X',
                    'Find people who stopped multiple times',
                    'Show erratic movement patterns'
                ]
            },
            {
                'type': 'compound_queries',
                'description': 'Complex multi-criteria searches',
                'examples': [
                    'People who entered after 5 PM AND stayed more than 2 minutes',
                    'Find person with red cap OR blue jacket near entrance',
                    'Show people who appear in multiple cameras AND carry bags'
                ]
            },
            {
                'type': 'recurrence_queries',
                'description': 'Multiple appearance analysis',
                'examples': [
                    'Find people who appear more than once',
                    'Show the same person across different times',
                    'Identify repeat visitors'
                ]
            }
        ],
        
        'query_complexity_levels': {
            'simple': {
                'description': 'Single criteria searches',
                'processing_time': '1-3 seconds',
                'example': 'Find person in red shirt'
            },
            'compound': {
                'description': 'Multiple criteria with AND/OR logic',
                'processing_time': '3-8 seconds',
                'example': 'People after 5 PM who stayed more than 2 minutes'
            },
            'complex': {
                'description': 'Multi-stage analysis with behavioral patterns',
                'processing_time': '8-15 seconds',
                'example': 'Summarize movement patterns of people with bags'
            }
        },
        
        'response_format': {
            'investigation_id': 'Unique investigation identifier',
            'confidence': 'Overall confidence score (0.0-1.0)',
            'evidence': 'List of matching evidence items',
            'timeline': 'Chronological timeline of events',
            'clips': 'Video evidence clips',
            'insights': 'AI-generated insights and observations',
            'ai_analysis': 'Detailed AI reasoning and execution plan'
        }
    }


@router.get("/examples")
async def get_query_examples() -> Dict[str, List[str]]:
    """
    Get example queries for different use cases
    
    Returns:
        Categorized example queries
    """
    
    return {
        'retail_security': [
            'Find the person who stayed near the jewelry counter for more than 5 minutes',
            'Show everyone who entered through the back entrance after closing time',
            'Find people who appear multiple times but never make purchases',
            'Identify individuals with large bags near expensive merchandise'
        ],
        
        'general_surveillance': [
            'Track the movement of the person in the red jacket',
            'Find everyone who entered the restricted area',
            'Show people who were present during the incident time',
            'Identify individuals who left immediately after the alarm'
        ],
        
        'behavioral_analysis': [
            'Find people exhibiting unusual movement patterns',
            'Show individuals who stopped multiple times in the same area',
            'Identify people who spent time near multiple exits',
            'Find visitors with significantly different behavior from others'
        ],
        
        'temporal_investigations': [
            'Show all activity between 10 PM and 6 AM',
            'Find people present during both morning and evening shifts',
            'Identify late-night visitors who stayed more than 30 minutes',
            'Show everyone who was here when the building was supposed to be empty'
        ],
        
        'multi_criteria_searches': [
            'People with backpacks who entered after 6 PM and stayed less than 10 minutes',
            'Find individuals in dark clothing who avoided the main entrance',
            'Show people who appeared on multiple cameras but never in the main area',
            'Identify visitors who came in groups but left separately'
        ]
    }


@router.post("/investigate/batch")
@harden_api_endpoint("ai_batch_investigate")
async def batch_investigation(
    queries: list = Form(..., description="List of investigation queries"),
    video_id: Optional[str] = Form(None, description="Optional video ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Process multiple investigation queries in batch
    
    Args:
        queries: List of investigation queries
        video_id: Optional video ID to limit scope
        db: Database session
        
    Returns:
        Batch investigation results
    """
    
    if not queries or len(queries) == 0:
        raise HTTPException(status_code=400, detail="At least one query required")
    
    if len(queries) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 queries per batch")
    
    context = {'video_id': video_id} if video_id else {}
    batch_results = []
    
    for i, query in enumerate(queries):
        try:
            result = ai_investigation_agent.investigate(
                user_query=query,
                db=db,
                context=context,
                max_results=20  # Reduced for batch processing
            )
            
            batch_results.append({
                'query_index': i,
                'query': query,
                'status': result.status,
                'matches': len(result.evidence),
                'confidence': result.confidence,
                'investigation_id': result.investigation_id
            })
            
        except Exception as e:
            batch_results.append({
                'query_index': i,
                'query': query,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'batch_id': f"batch_{uuid.uuid4()}",
        'total_queries': len(queries),
        'successful_queries': len([r for r in batch_results if r['status'] == 'success']),
        'results': batch_results,
        'timestamp': datetime.now().isoformat()
    }