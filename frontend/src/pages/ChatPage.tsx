import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ChatBox from "../components/chat/ChatBox";
import ConversationSidebar from "../components/chat/ConversationSidebar";
import { MessageProps, MessageCitation } from "../components/chat/MessageItem";
import {
  listConversations,
  getConversation,
  deleteConversation,
  queryRAG,
} from "../services/chatService";
import { ConversationResponse, ConversationDetailResponse } from "../types/chat";

export const ChatPage: React.FC = () => {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();

  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [loadingConversations, setLoadingConversations] = useState<boolean>(true);
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);

  const [activeConversation, setActiveConversation] = useState<ConversationDetailResponse | null>(null);
  const [messages, setMessages] = useState<MessageProps[]>([]);
  const [loadingChat, setLoadingChat] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all user conversations
  const fetchConversations = async () => {
    try {
      setLoadingConversations(true);
      const res = await listConversations();
      setConversations(res.items);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, []);

  // Sync active conversation when URL param changes
  useEffect(() => {
    if (!conversationId) {
      setActiveConversation(null);
      setMessages([]);
      setError(null);
      return;
    }

    const loadConversationDetail = async () => {
      try {
        setLoadingChat(true);
        setError(null);
        const data = await getConversation(conversationId);
        setActiveConversation(data);

        // Map stored database messages to UI MessageProps with preserved citations
        const formattedMessages: MessageProps[] = data.messages.map((m) => {
          const citations: MessageCitation[] = (m.metadata?.citations && m.metadata.citations.length > 0)
            ? m.metadata.citations.map((c: any) => ({
                citationId: c.citation_id,
                sourceName: c.document_filename,
                page: c.page_number,
                rawCitation: c,
              }))
            : (m.metadata?.sources || []).map((s: any) => ({
                citationId: s.citation_id,
                sourceName: s.document_filename,
                page: s.page_number,
                rawCitation: {
                  citation_id: s.citation_id,
                  document_id: s.document_id,
                  document_filename: s.document_filename,
                  chunk_id: s.chunk_id,
                  chunk_index: s.chunk_index,
                  page_number: s.page_number,
                  similarity_score: s.similarity_score,
                  cosine_distance: s.cosine_distance,
                  metadata: s.metadata,
                },
              }));

          return {
            role: m.role as "user" | "assistant" | "system",
            content: m.content,
            citations,
            timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          };
        });

        setMessages(formattedMessages);
      } catch (err: any) {
        console.error("Failed to load conversation details:", err);
        setError("Conversation not found or access denied.");
        navigate("/chat", { replace: true });
      } finally {
        setLoadingChat(false);
      }
    };

    loadConversationDetail();
  }, [conversationId, navigate]);

  const handleSelectConversation = (id: string) => {
    navigate(`/chat/${id}`);
  };

  const handleNewChat = () => {
    setActiveConversation(null);
    setMessages([]);
    setError(null);
    navigate("/chat");
  };

  const handleDeleteConversation = async (id: string) => {
    await deleteConversation(id);
    await fetchConversations();
    if (conversationId === id) {
      handleNewChat();
    }
  };

  const handleSendMessage = async (query: string) => {
    setError(null);
    const userTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMessage: MessageProps = {
      role: "user",
      content: query,
      timestamp: userTimestamp,
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoadingChat(true);

    try {
      const response = await queryRAG({
        query,
        conversation_id: activeConversation?.id || conversationId || null,
      });

      const assistantTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      const citations: MessageCitation[] = (response.citations && response.citations.length > 0)
        ? response.citations.map((c) => ({
            citationId: c.citation_id,
            sourceName: c.document_filename,
            page: c.page_number,
            rawCitation: c,
          }))
        : (response.sources || []).map((s) => ({
            citationId: s.citation_id,
            sourceName: s.document_filename,
            page: s.page_number,
            rawCitation: {
              citation_id: s.citation_id,
              document_id: s.document_id,
              document_filename: s.document_filename,
              chunk_id: s.chunk_id,
              chunk_index: s.chunk_index,
              page_number: s.page_number,
              similarity_score: s.similarity_score,
              cosine_distance: s.cosine_distance,
              metadata: s.metadata,
            },
          }));

      const assistantMessage: MessageProps = {
        role: "assistant",
        content: response.answer,
        citations,
        timestamp: assistantTimestamp,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If a new conversation was created by the backend, update URL and list
      if (response.conversation_id && response.conversation_id !== conversationId) {
        navigate(`/chat/${response.conversation_id}`, { replace: true });
        await fetchConversations();
      } else {
        // Refresh conversation list to bump updated_at
        fetchConversations();
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMsg = typeof detail === "string" ? detail : "Failed to generate answer. Please check LLM provider configuration or try again.";
      setError(errorMsg);
    } finally {
      setLoadingChat(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-10rem)] bg-white border border-slate-200/90 rounded-2xl shadow-xs overflow-hidden">
      {/* Conversation History Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeId={conversationId || null}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        loading={loadingConversations}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Chat Stream */}
      <div className="flex-1 flex flex-col min-w-0">
        <ChatBox
          messages={messages}
          conversationTitle={activeConversation?.title}
          conversationId={conversationId || null}
          onSendMessage={handleSendMessage}
          loading={loadingChat}
          error={error}
          onToggleSidebar={() => setSidebarOpen(true)}
          showSidebarToggle={true}
        />
      </div>
    </div>
  );
};

export default ChatPage;
