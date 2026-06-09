#include <cstring>
#include <iostream>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

using namespace std;
#define PORT 8080


int main(){
	
	char buffer[1024] = {0};

	int sockfd = socket(AF_INET,SOCK_STREAM,0);
	
	if(sockfd<0){
		perror("socket couldn't be created");
		exit(0);
	}

	//specifying the server's address
	sockaddr_in serveraddress{};
	serveraddress.sin_family = AF_INET;
	serveraddress.sin_port = htons(8080);
	serveraddress.sin_addr.s_addr = INADDR_ANY;

	//binding the socket
	cout << "binding\n";
	if(bind(sockfd, (struct sockaddr *)&serveraddress, sizeof(serveraddress))<0){
		perror("couldn't bind ");
		exit(EXIT_FAILURE);

	}
	

	//listenting to the server socket
	cout << "listening\n";
	if(listen(sockfd, 5)<0){
		perror("error while listening");
		exit(0);
	}
	

	//accepting clients
	//int clientsocket = accept(sockfd, (struct sockaddr *)&clientaddr, sizeof(clientaddr));
	cout << "waiting for client" << endl;
	int clientsocket = accept(sockfd, nullptr, nullptr);
	if(clientsocket<0){
		perror("couldn't accept client");
		exit(0);
	}

	//receiving from the client
	cout << "receiving\n";
	recv(clientsocket, buffer, sizeof(buffer),0);
	cout << "message from client : " << buffer << endl;

	//closing the server and the client
	close(sockfd);
	close(clientsocket);

}
