#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstring>
#include <iostream>
using namespace std;
#define PORT 8080

int main(){

	string msg = "hello from client";
	
	int clientsocket = socket(AF_INET, SOCK_STREAM, 0);
	if(clientsocket<0){
		cerr << "couldn't create socket\n"; 
		exit(EXIT_FAILURE);
	}
	cout << "socket initialized\n";
	sockaddr_in serveraddr{};
	serveraddr.sin_family = AF_INET;
	serveraddr.sin_port = htons(PORT);
	inet_pton(AF_INET,
          "127.0.0.1",
          &serveraddr.sin_addr);	
	if(connect(clientsocket, (struct sockaddr *)&serveraddr, sizeof(serveraddr))<0){
		cerr << "couldn't connect to server";
		exit(0);
	}
	cout << "connected to server\n";
	send(clientsocket, msg.c_str(),msg.length(),0);
	cout<< "message sent \n" ;
	close(clientsocket);
	return 0;
}
