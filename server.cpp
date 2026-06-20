#include <arpa/inet.h>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

using namespace std;

constexpr int PORT = 8080;
constexpr size_t BUFFER_SIZE = 4096;
constexpr uint32_t MAX_FILE_NAME_SIZE = 255;

uint64_t from_network64(uint64_t value) {
    static const int num = 42;
    const bool little_endian = *reinterpret_cast<const char *>(&num) == 42;

    if (!little_endian) {
        return value;
    }

    uint64_t result = 0;
    for (int i = 0; i < 8; ++i) {
        result = (result << 8) | (value & 0xff);
        value >>= 8;
    }
    return result;
}

bool recv_all(int socket_fd, void *data, size_t length) {
    char *buffer = static_cast<char *>(data);
    size_t received_total = 0;

    while (received_total < length) {
        ssize_t received = recv(socket_fd, buffer + received_total, length - received_total, 0);
        if (received <= 0) {
            return false;
        }
        received_total += static_cast<size_t>(received);
    }

    return true;
}

string safe_file_name(const string &name) {
    filesystem::path path(name);
    string base_name = path.filename().string();
    return base_name.empty() ? "received_file" : base_name;
}

int main() {
    int server_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (server_socket < 0) {
        perror("socket");
        return 1;
    }

    int reuse = 1;
    setsockopt(server_socket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    server_addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(server_socket, reinterpret_cast<sockaddr *>(&server_addr), sizeof(server_addr)) < 0) {
        perror("bind");
        close(server_socket);
        return 1;
    }

    if (listen(server_socket, 5) < 0) {
        perror("listen");
        close(server_socket);
        return 1;
    }

    cout << "server listening on port " << PORT << "\n";
    cout << "waiting for a file...\n";

    sockaddr_in client_addr{};
    socklen_t client_addr_len = sizeof(client_addr);
    int client_socket = accept(server_socket, reinterpret_cast<sockaddr *>(&client_addr), &client_addr_len);
    if (client_socket < 0) {
        perror("accept");
        close(server_socket);
        return 1;
    }

    char client_ip[INET_ADDRSTRLEN] = {};
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
    cout << "connected to client " << client_ip << "\n";

    uint32_t network_name_size = 0;
    uint64_t network_file_size = 0;

    if (!recv_all(client_socket, &network_name_size, sizeof(network_name_size)) ||
        !recv_all(client_socket, &network_file_size, sizeof(network_file_size))) {
        cerr << "error: failed to receive file header\n";
        close(client_socket);
        close(server_socket);
        return 1;
    }

    const uint32_t file_name_size = ntohl(network_name_size);
    const uint64_t file_size = from_network64(network_file_size);

    if (file_name_size == 0 || file_name_size > MAX_FILE_NAME_SIZE) {
        cerr << "error: invalid file name size\n";
        close(client_socket);
        close(server_socket);
        return 1;
    }

    string file_name(file_name_size, '\0');
    if (!recv_all(client_socket, file_name.data(), file_name.size())) {
        cerr << "error: failed to receive file name\n";
        close(client_socket);
        close(server_socket);
        return 1;
    }

    const string output_name = "received_" + safe_file_name(file_name);
    ofstream output(output_name, ios::binary);
    if (!output.is_open()) {
        cerr << "error: unable to create output file: " << output_name << "\n";
        close(client_socket);
        close(server_socket);
        return 1;
    }

    char buffer[BUFFER_SIZE];
    uint64_t total_received = 0;

    while (total_received < file_size) {
        const size_t remaining = static_cast<size_t>(min<uint64_t>(sizeof(buffer), file_size - total_received));
        ssize_t received = recv(client_socket, buffer, remaining, 0);

        if (received <= 0) {
            cerr << "error: connection closed before file was fully received\n";
            close(client_socket);
            close(server_socket);
            return 1;
        }

        output.write(buffer, received);
        total_received += static_cast<uint64_t>(received);
    }

    cout << "saved " << output_name << " (" << total_received << " bytes)\n";

    close(client_socket);
    close(server_socket);
    return 0;
}
