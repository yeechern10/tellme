from langchain_openai import OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings

from ..domain.entities import ArticleModel, EventModel, KeywordModel
from uuid import UUID

from ..core.config import EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE

def keyword_dicts_to_text(keyword_dicts):
    keywords_texts = []
    for _, details in keyword_dicts.items():
        keyword_name = details["label"]
        keyword_description = details["definition"]
        keyword_synonyms = details["synonyms"]
        parents = []
        parent_id = details["parent"]
        while parent_id:
            parent_details = keyword_dicts.get(parent_id)
            if parent_details:
                parents.append(parent_details["label"])
                parent_id = parent_details["parent"]
            else:
                break
        
        text = f"{keyword_name}\n{keyword_description}:{', '.join(keyword_synonyms)}\n{' > '.join(parents[::-1])}\n"
        keywords_texts.append(text)
    return keywords_texts

def embedding_keywords(keyword_dicts) -> dict[UUID, dict]:
    keywords_texts = keyword_dicts_to_text(keyword_dicts)
    
    embedding = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": EMBEDDING_BATCH_SIZE,
        }
    )

    doc_vectors = embedding.embed_documents(keywords_texts)
    for i, keyword_id in enumerate(keyword_dicts.keys()):
        keyword_dicts[keyword_id]["embedding"] = doc_vectors[i]
    
    return keyword_dicts

def article_title_content_to_text(article: ArticleModel):
    if article.content:
        text = f"Title: {article.title}\nContent: {article.content}\n"
    else:
        text = f"Title: {article.title}\nSnippet: {article.snippet}\n"
    return text

def embedding_articles(article_dicts: dict[UUID, ArticleModel], to_embedding_articles: list[UUID]):
    embedding = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": EMBEDDING_BATCH_SIZE,
        }
    )

    article_texts = [article_title_content_to_text(article_dicts[article_id]) for article_id in to_embedding_articles]
    article_vectors = embedding.embed_documents(article_texts)
    
    for i, article_id in enumerate(to_embedding_articles):
        article_dicts[article_id].embedding = article_vectors[i]
        article_dicts[article_id].embedded = True  # Mark the article as embedded
    
    return article_dicts

def embedding_event(event: EventModel):
    embedding = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": EMBEDDING_BATCH_SIZE,
        }
    )

    event_text = f"Title: {event.title}\nSummary: {event.summary}\n"
    event_vector = embedding.embed_documents([event_text])[0]
    
    event.embedding = event_vector
    event.embedded = True  # Mark the event as embedded
    
    return event