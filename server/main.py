from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from chains.retrieval_chain import ingest_docs, build_chain
import os
import json
import asyncio

# Initialize chain (will be built when first used)
chain = None
app = FastAPI()

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestPayload(BaseModel):
    resume: str
    job: str
    info: dict

@app.post("/ingest")
async def ingest(payload: IngestPayload):
    """Ingest resume and job description into vector store"""
    try:
        # Ensure data directory exists
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Save resume and job description
        with open(os.path.join(data_dir, "resume.txt"), "w", encoding="utf-8") as f:
            f.write(payload.resume)
        
        with open(os.path.join(data_dir, "job.txt"), "w", encoding="utf-8") as f:
            f.write(payload.job)
        
        # Save profile info if provided
        if payload.info:
            with open(os.path.join(data_dir, "profile.json"), "w", encoding="utf-8") as f:
                json.dump(payload.info, f, indent=2)
        
        # Ingest documents into vector store
        ingest_docs()
        
        # Rebuild chain with new data
        global chain
        chain = build_chain()
        
        return {"status": "ok", "message": "Documents ingested successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.websocket("/stream")
async def stream(ws: WebSocket):
    """WebSocket endpoint for streaming interview suggestions"""
    await ws.accept()
    chat_history = []
    api_key = None
    
    try:
        # Initialize chain if not already done
        global chain
        if chain is None:
            try:
                chain = build_chain()
            except Exception as e:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": f"Failed to initialize chain: {str(e)}. Please ingest documents first."
                }))
                await ws.close()
                return
        
        while True:
            try:
                # Receive message from client
                data = await ws.receive_text()
                message = json.loads(data)
                
                # Handle API key setting
                if message.get("type") == "api_key":
                    api_key = message.get("key")
                    os.environ["OPENAI_API_KEY"] = api_key
                    # Rebuild chain with new API key
                    chain = build_chain()
                    await ws.send_text(json.dumps({
                        "type": "status",
                        "message": "API key set successfully"
                    }))
                    continue
                
                # Handle caption text
                if message.get("type") == "caption":
                    question = message.get("text", "")
                    if not question or len(question.strip()) < 10:
                        continue
                    
                    try:
                        # Get suggestion from chain
                        result = chain.invoke({
                            "question": question,
                            "chat_history": chat_history
                        })
                        
                        answer = result.get("answer", "")
                        
                        if answer:
                            # Stream the answer in chunks for better UX
                            words = answer.split()
                            chunk_size = 5
                            
                            for i in range(0, len(words), chunk_size):
                                chunk = " ".join(words[i:i + chunk_size]) + " "
                                await ws.send_text(json.dumps({
                                    "type": "suggestion",
                                    "text": chunk
                                }))
                                await asyncio.sleep(0.1)  # Small delay for streaming effect
                            
                            # Update chat history
                            chat_history.append((question, answer))
                            
                            # Keep chat history manageable (last 10 exchanges)
                            if len(chat_history) > 10:
                                chat_history = chat_history[-10:]
                    
                    except Exception as e:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": f"Error processing question: {str(e)}"
                        }))
                        print(f"Error: {e}")
                
            except json.JSONDecodeError:
                # Handle plain text (backward compatibility)
                question = data
                if question and len(question.strip()) >= 10:
                    try:
                        result = chain.invoke({
                            "question": question,
                            "chat_history": chat_history
                        })
                        answer = result.get("answer", "")
                        if answer:
                            await ws.send_text(json.dumps({
                                "type": "suggestion",
                                "text": answer
                            }))
                            chat_history.append((question, answer))
                            if len(chat_history) > 10:
                                chat_history = chat_history[-10:]
                    except Exception as e:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": str(e)
                        }))
    
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await ws.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        try:
            await ws.close()
        except:
            pass

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
