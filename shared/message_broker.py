import json
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime

# Import models for type hints
from .models import EventMessage

class MessageBroker(ABC):
    """Abstract base class for message brokers"""
    
    @abstractmethod
    async def connect(self):
        """Connect to the message broker"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the message broker"""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, message: EventMessage):
        """
        Publish a message to a topic
        
        Args:
            topic (str): Topic to publish to
            message (EventMessage): Message to publish
        """
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to a topic
        
        Args:
            topic (str): Topic to subscribe to
            callback (Callable): Function to call when a message is received
        """
        pass

class InMemoryMessageBroker(MessageBroker):
    """In-memory message broker for development and testing"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.connected = False
    
    async def connect(self):
        """Connect to the in-memory message broker"""
        self.connected = True
        self.logger.info("Connected to in-memory message broker")
    
    async def disconnect(self):
        """Disconnect from the in-memory message broker"""
        self.connected = False
        self.logger.info("Disconnected from in-memory message broker")
    
    async def publish(self, topic: str, message: EventMessage):
        """
        Publish a message to a topic
        
        Args:
            topic (str): Topic to publish to
            message (EventMessage): Message to publish
        """
        if not self.connected:
            raise RuntimeError("Not connected to message broker")
        
        self.logger.debug(f"Publishing message to topic {topic}: {message}")
        
        # Convert message to dict for serialization
        message_dict = message.dict()
        
        # Call all subscribers for this topic
        if topic in self.subscriptions:
            for callback in self.subscriptions[topic]:
                try:
                    await callback(message_dict)
                except Exception as e:
                    self.logger.error(f"Error in subscriber callback: {e}")
    
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to a topic
        
        Args:
            topic (str): Topic to subscribe to
            callback (Callable): Function to call when a message is received
        """
        if not self.connected:
            raise RuntimeError("Not connected to message broker")
        
        self.logger.debug(f"Subscribing to topic {topic}")
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        
        self.subscriptions[topic].append(callback)

class KafkaMessageBroker(MessageBroker):
    """Kafka message broker implementation"""
    
    def __init__(self, bootstrap_servers: str, client_id: str, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self.producer = None
        self.consumer = None
        self.consumer_tasks = []
    
    async def connect(self):
        """Connect to Kafka"""
        try:
            # Import here to avoid dependency if not using Kafka
            from aiokafka import AIOKafkaProducer
            
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=f"{self.client_id}-producer"
            )
            await self.producer.start()
            self.logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except ImportError:
            self.logger.error("aiokafka package not installed. Please install with: pip install aiokafka")
            raise
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Kafka"""
        if self.producer:
            await self.producer.stop()
            self.producer = None
        
        # Cancel all consumer tasks
        for task in self.consumer_tasks:
            task.cancel()
        
        self.consumer_tasks = []
        self.logger.info("Disconnected from Kafka")
    
    async def publish(self, topic: str, message: EventMessage):
        """
        Publish a message to a Kafka topic
        
        Args:
            topic (str): Topic to publish to
            message (EventMessage): Message to publish
        """
        if not self.producer:
            raise RuntimeError("Not connected to Kafka")
        
        # Convert message to JSON string
        message_json = json.dumps(message.dict(), default=str).encode('utf-8')
        
        try:
            await self.producer.send_and_wait(topic, message_json)
            self.logger.debug(f"Published message to topic {topic}")
        except Exception as e:
            self.logger.error(f"Failed to publish message to topic {topic}: {e}")
            raise
    
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to a Kafka topic
        
        Args:
            topic (str): Topic to subscribe to
            callback (Callable): Function to call when a message is received
        """
        if not self.producer:  # Using producer as a check for connection
            raise RuntimeError("Not connected to Kafka")
        
        # Import here to avoid dependency if not using Kafka
        from aiokafka import AIOKafkaConsumer
        
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=f"{self.client_id}-consumer",
            auto_offset_reset="latest"
        )
        
        await consumer.start()
        self.logger.info(f"Subscribed to Kafka topic {topic}")
        
        # Create a task to consume messages
        task = asyncio.create_task(self._consume(consumer, callback))
        self.consumer_tasks.append(task)
    
    async def _consume(self, consumer, callback):
        """
        Consume messages from Kafka
        
        Args:
            consumer: Kafka consumer
            callback (Callable): Function to call when a message is received
        """
        try:
            async for msg in consumer:
                try:
                    # Parse message JSON
                    message_dict = json.loads(msg.value.decode('utf-8'))
                    
                    # Call callback with message
                    await callback(message_dict)
                except json.JSONDecodeError:
                    self.logger.error(f"Failed to decode message: {msg.value}")
                except Exception as e:
                    self.logger.error(f"Error in subscriber callback: {e}")
        except asyncio.CancelledError:
            # Task was cancelled, clean up
            await consumer.stop()
        except Exception as e:
            self.logger.error(f"Error consuming messages: {e}")
            await consumer.stop()

class RabbitMQMessageBroker(MessageBroker):
    """RabbitMQ message broker implementation"""
    
    def __init__(self, host: str, port: int = 5672, username: str = 'guest', 
                 password: str = 'guest', virtual_host: str = '/', logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.virtual_host = virtual_host
        self.connection = None
        self.channel = None
        self.consumer_tags = []
    
    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            # Import here to avoid dependency if not using RabbitMQ
            import aio_pika
            
            self.connection = await aio_pika.connect_robust(
                host=self.host,
                port=self.port,
                login=self.username,
                password=self.password,
                virtualhost=self.virtual_host
            )
            
            self.channel = await self.connection.channel()
            self.logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
        except ImportError:
            self.logger.error("aio_pika package not installed. Please install with: pip install aio-pika")
            raise
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None
            self.consumer_tags = []
            self.logger.info("Disconnected from RabbitMQ")
    
    async def publish(self, topic: str, message: EventMessage):
        """
        Publish a message to a RabbitMQ exchange
        
        Args:
            topic (str): Exchange to publish to
            message (EventMessage): Message to publish
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
        
        try:
            # Import here to avoid dependency if not using RabbitMQ
            import aio_pika
            
            # Ensure exchange exists
            exchange = await self.channel.declare_exchange(
                topic,
                aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Convert message to JSON string
            message_json = json.dumps(message.dict(), default=str).encode('utf-8')
            
            # Create message
            message = aio_pika.Message(
                body=message_json,
                content_type="application/json"
            )
            
            # Publish message
            await exchange.publish(message, routing_key="")
            self.logger.debug(f"Published message to exchange {topic}")
        except Exception as e:
            self.logger.error(f"Failed to publish message to exchange {topic}: {e}")
            raise
    
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to a RabbitMQ exchange
        
        Args:
            topic (str): Exchange to subscribe to
            callback (Callable): Function to call when a message is received
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
        
        try:
            # Import here to avoid dependency if not using RabbitMQ
            import aio_pika
            
            # Ensure exchange exists
            exchange = await self.channel.declare_exchange(
                topic,
                aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Create queue
            queue = await self.channel.declare_queue(exclusive=True)
            
            # Bind queue to exchange
            await queue.bind(exchange)
            
            # Start consuming
            consumer_tag = await queue.consume(
                lambda message: self._on_message(message, callback)
            )
            
            self.consumer_tags.append(consumer_tag)
            self.logger.info(f"Subscribed to RabbitMQ exchange {topic}")
        except Exception as e:
            self.logger.error(f"Failed to subscribe to exchange {topic}: {e}")
            raise
    
    async def _on_message(self, message, callback):
        """
        Handle incoming RabbitMQ message
        
        Args:
            message: RabbitMQ message
            callback (Callable): Function to call with message
        """
        async with message.process():
            try:
                # Parse message JSON
                message_dict = json.loads(message.body.decode('utf-8'))
                
                # Call callback with message
                await callback(message_dict)
            except json.JSONDecodeError:
                self.logger.error(f"Failed to decode message: {message.body}")
            except Exception as e:
                self.logger.error(f"Error in subscriber callback: {e}")

def create_message_broker(broker_type: str, config: Dict[str, Any], logger=None) -> MessageBroker:
    """
    Factory function to create a message broker
    
    Args:
        broker_type (str): Type of message broker ('memory', 'kafka', 'rabbitmq')
        config (Dict[str, Any]): Configuration for the message broker
        logger (logging.Logger, optional): Logger to use
        
    Returns:
        MessageBroker: Message broker instance
    """
    if broker_type == 'memory':
        return InMemoryMessageBroker(logger=logger)
    elif broker_type == 'kafka':
        return KafkaMessageBroker(
            bootstrap_servers=config.get('bootstrap_servers', 'localhost:9092'),
            client_id=config.get('client_id', 'rc-zoho'),
            logger=logger
        )
    elif broker_type == 'rabbitmq':
        return RabbitMQMessageBroker(
            host=config.get('host', 'localhost'),
            port=config.get('port', 5672),
            username=config.get('username', 'guest'),
            password=config.get('password', 'guest'),
            virtual_host=config.get('virtual_host', '/'),
            logger=logger
        )
    else:
        raise ValueError(f"Unknown message broker type: {broker_type}")