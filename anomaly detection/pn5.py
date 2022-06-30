# Poisoning attack simulations: non-malicious federated client

import warnings
from collections import OrderedDict
import flwr as fl
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision.transforms import Compose, Normalize, ToTensor, Resize, RandomRotation, CenterCrop
from tqdm import tqdm
import os

warnings.filterwarnings("ignore", category=UserWarning)
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv_a = nn.Conv2d(in_channels=3, out_channels=12, kernel_size=3, stride=1, padding=1)
        self.batch_a = nn.BatchNorm2d(num_features=12)
        self.relu_a = nn.ReLU()
        self.max_a = nn.MaxPool2d(kernel_size=2)
        self.conv_b = nn.Conv2d(in_channels=12, out_channels=20, kernel_size=3, stride=1, padding=1)
        self.relu_b = nn.ReLU()
        self.conv_c = nn.Conv2d(in_channels=20, out_channels=32, kernel_size=3, stride=1, padding=1)
        self.batch_b = nn.BatchNorm2d(num_features=32)
        self.relu_c = nn.ReLU()
        self.fc = nn.Linear(in_features=32 * 112 * 112, out_features=2)

    def forward(self, input):
        output = self.conv_a(input)
        output = self.batch_a(output)
        output = self.relu_a(output)
        output = self.max_a(output)
        output = self.conv_b(output)
        output = self.relu_b(output)
        output = self.conv_c(output)
        output = self.batch_b(output)
        output = self.relu_c(output)
        output = output.view(-1, 32 * 112 * 112)
        output = self.fc(output)

        return output


def train(net, trainloader, epochs):
    print("train")
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(net.parameters(), lr=0.005, momentum=0.0)
    for _ in range(epochs):
        for images, labels in tqdm(trainloader):
            optimizer.zero_grad()
            criterion(net(images.to(DEVICE)), labels.to(DEVICE)).backward()
            optimizer.step()


def test(net, testloader):
    print("test")
    criterion = torch.nn.CrossEntropyLoss()
    correct, total, loss = 0, 0, 0.0
    with torch.no_grad():
        for images, labels in tqdm(testloader):
            outputs = net(images.to(DEVICE))
            labels = labels.to(DEVICE)
            loss += criterion(outputs, labels).item()
            total += labels.size(0)
            correct += (torch.max(outputs.data, 1)[1] == labels).sum().item()
    return loss / len(testloader.dataset), correct / total


def load_data():
    transform_train = Compose(
        [
            Resize(size = (256,256)),
            RandomRotation(degrees = (-3,+3)),
            CenterCrop(size=224),
            ToTensor(),
            Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])
        ])
    transform_test = Compose(
        [
            Resize(size = (224,224)),
            ToTensor(),
            Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])
        ])

    folder = os.path.basename(__file__)[:-3]  # on remove le .py
    trainset = datasets.ImageFolder(root='mydata/'+folder+'/train', transform=transform_train)
    testset = datasets.ImageFolder(root='mydata/pn_old/'+folder+'/test', transform=transform_test)

    return DataLoader(trainset, batch_size=16, shuffle=True), DataLoader(testset, batch_size=8)


net = Net().to(DEVICE)
trainloader, testloader = load_data()


# defintition of the client
class FlowerClient(fl.client.NumPyClient):
    def get_parameters(self):
        return [val.cpu().numpy() for _, val in net.state_dict().items()]

    def set_parameters(self, parameters):
        params_dict = zip(net.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
        net.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        self.set_parameters(parameters)
        train(net, trainloader, epochs=5)
        return self.get_parameters(), len(trainloader.dataset), {}

    def evaluate(self, parameters, config):
        self.set_parameters(parameters)
        loss, accuracy = test(net, testloader)
        return loss, len(testloader.dataset), {"accuracy": accuracy, "loss": loss}


# demarrage du client
fl.client.start_numpy_client("localhost:8080", client=FlowerClient())